from flask import Blueprint,jsonify,request
from flask_jwt_extended import jwt_required,get_jwt_identity
from app.models import User, FriendRequest
from sqlalchemy import or_
from werkzeug.utils import secure_filename
from app.utils.helpers import allowed_file
from app import db
from flask import current_app
import os
user_bp = Blueprint('user', __name__)

@user_bp.route('/api/users', methods=['GET'])
@jwt_required()
def get_all_users():
    current_user_id = int(get_jwt_identity())
    search_term = request.args.get('search', '')

    query = User.query.filter(User.id != current_user_id)

    if search_term:
        query = query.filter(
            or_(
                User.username.ilike(f'%{search_term}%'),
                User.email.ilike(f'%{search_term}%')
            )
        )

    users = query.all()

    def get_status(other_user_id):
        fr = FriendRequest.query.filter(
            ((FriendRequest.sender_id == current_user_id) & (FriendRequest.receiver_id == other_user_id)) |
            ((FriendRequest.sender_id == other_user_id) & (FriendRequest.receiver_id == current_user_id))
        ).first()

        if not fr:
            return "none"
        elif fr.status == "pending":
            return "sent" if fr.sender_id == current_user_id else "received"
        elif fr.status == "accepted":
            return "friends"
        else:
            return "rejected"

    result = []
    for user in users:
        result.append({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'profile_picture': user.profile_picture,
            'friendship_status': get_status(user.id)
        })

    return jsonify(result), 200


@user_bp.route('/api/users/upload-profile', methods=['POST'])
@jwt_required()
def upload_profile_picture():
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)

    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        # Make filename unique
        filename = f"user_{user_id}_{filename}"
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)

        user.profile_picture = f"/static/uploads/{filename}"
        # Save path in DB
        db.session.commit()

        return jsonify({'message': 'Profile picture uploaded successfully', 'profile_picture': user.profile_picture}), 200
    

    return jsonify({'error': 'Invalid file type'}), 400


@user_bp.route('/api/users/me', methods=['PUT'])
@jwt_required()
def update_my_profile():
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)

    data = request.json or {}
    user.bio = data.get('bio', user.bio)
    user.location = data.get('location', user.location)
    user.status = data.get('status', user.status)

    db.session.commit()

    return jsonify({
        'message': 'Profile updated',
        'user': {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'bio': user.bio,
            'location': user.location,
            'status': user.status,
            'profile_picture': user.profile_picture
        }
    }), 200


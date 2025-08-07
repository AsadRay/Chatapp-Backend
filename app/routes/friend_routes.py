from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.models import User, FriendRequest
from datetime import datetime
from sqlalchemy import or_

friend_bp = Blueprint('friend', __name__)

# Send Friend Request
@friend_bp.route('/api/friends/request', methods=['POST'])
@jwt_required()
def send_friend_request():
    data = request.get_json()
    receiver_id = data.get('receiver_id')
    sender_id = get_jwt_identity()

    if not receiver_id or receiver_id == sender_id:
        return jsonify({'error': 'Invalid request'}), 400

    # Check if already requested or friends
    existing = FriendRequest.query.filter_by(sender_id=sender_id, receiver_id=receiver_id).first()
    if existing:
        return jsonify({'error': 'Request already sent or exists'}), 400

    friend_request = FriendRequest(sender_id=sender_id, receiver_id=receiver_id)
    db.session.add(friend_request)
    db.session.commit()

    return jsonify({'message': 'Friend request sent'}), 201


# View Incoming Requests
@friend_bp.route('/api/friends/requests', methods=['GET'])
@jwt_required()
def get_friend_requests():
    user_id = get_jwt_identity()
    requests = FriendRequest.query.filter_by(receiver_id=user_id, status='pending').all()

    print("📥 Found requests:", requests)

    result = [{
        'id': req.id,
        'sender_id': req.sender_id,
        'sender_username': req.sender.username
    } for req in requests]

    return jsonify(result), 200


# Accept/Reject Friend Request
@friend_bp.route('/api/friends/respond', methods=['POST'])
@jwt_required()
def respond_to_request():
    data = request.get_json()
    request_id = data.get('request_id')
    action = data.get('action')  # 'accept' or 'reject'
    user_id = int(get_jwt_identity())
    req = FriendRequest.query.get(request_id)

    if not req or req.receiver_id != user_id or req.status != 'pending':
        return jsonify({'error': 'Request not found'}), 404

    if action == 'accept':
        req.status = 'accepted'
        req.accepted_at = datetime.utcnow()
    elif action == 'reject':
        req.status = 'rejected'
    else:
        return jsonify({'error': 'Invalid action'}), 400

    db.session.commit()
    return jsonify({'message': f'Request {action}ed'}), 200


@friend_bp.route('/api/friends', methods=['GET'])
@jwt_required()
def get_friends():
    user_id = int(get_jwt_identity())

    # Get page and limit from query params
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('limit', 10))

    query = FriendRequest.query.filter(
        FriendRequest.status == 'accepted',
        or_(
            FriendRequest.sender_id == user_id,
            FriendRequest.receiver_id == user_id
        )
    )

    paginated = query.paginate(page=page, per_page=per_page, error_out=False)
    requests = paginated.items

    friends = []
    for req in requests:
        # Pick the other user in the friendship
        friend = User.query.get(req.receiver_id if req.sender_id == user_id else req.sender_id)

        # Handle case where friend might not exist
        if not friend:
            continue

        friends.append({
            'id': friend.id,
            'username': friend.username,
            'email': friend.email,
            'profile_picture': friend.profile_picture,
            'bio': friend.bio,
            'location': friend.location,
            'status': friend.status,
            # Fixed: Add null check for accepted_at
            'friendship_accepted_at': req.accepted_at.strftime('%Y-%m-%d %H:%M') if req.accepted_at else None
        })

    return jsonify({
        'friends': friends,
        'total': paginated.total,
        'pages': paginated.pages,
        'current_page': paginated.page
    }), 200


@friend_bp.route('/api/friends/<int:friend_id>', methods=['DELETE'])
@jwt_required()
def unfriend(friend_id):
    user_id = int(get_jwt_identity())

    # Find the friendship regardless of who sent/received
    friendship = FriendRequest.query.filter(
        FriendRequest.status == 'accepted',
        ((FriendRequest.sender_id == user_id) & (FriendRequest.receiver_id == friend_id)) |
        ((FriendRequest.sender_id == friend_id) & (FriendRequest.receiver_id == user_id))
    ).first()

    if not friendship:
        return jsonify({'error': 'Friendship not found'}), 404

    db.session.delete(friendship)
    db.session.commit()

    return jsonify({'message': 'Unfriended successfully'}), 200
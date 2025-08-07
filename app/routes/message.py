from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models import Message
from app import db
from datetime import datetime
from flask import url_for

messages_bp = Blueprint('messages', __name__)

@messages_bp.route('/api/messages/send', methods=['POST'])
@jwt_required()
def send_message():
    data = request.get_json()
    sender_id = get_jwt_identity()  # Get from JWT token instead
    receiver_id = data.get('receiver_id')
    content = data.get('content')

    if not all([receiver_id, content]):
        return jsonify({'error': 'Missing required fields'}), 400

    message = Message(
        sender_id=sender_id,
        receiver_id=receiver_id,
        content=content,
        timestamp=datetime.utcnow()
    )
    db.session.add(message)
    db.session.commit()

    return jsonify({
        'id': message.id,
        'sender_id': sender_id,
        'receiver_id': receiver_id,
        'content': content,
        'timestamp': message.timestamp.strftime('%Y-%m-%d %H:%M:%S')
    }), 201

@messages_bp.route('/api/messages/chat', methods=['GET'])
@jwt_required()
def get_chat():
    current_user_id = get_jwt_identity()
    other_user_id = request.args.get('user2')
    page = request.args.get('page', default=1, type=int)
    per_page = request.args.get('per_page', default=20, type=int)
    order = request.args.get('order', default='desc')

    if not other_user_id:
        return jsonify({'error': 'Missing user2 ID'}), 400

    query = Message.query.filter(
        ((Message.sender_id == current_user_id) & (Message.receiver_id == other_user_id)) |
        ((Message.sender_id == other_user_id) & (Message.receiver_id == current_user_id))
    )

    if order == 'asc':
        query = query.order_by(Message.timestamp.asc())
    else:
        query = query.order_by(Message.timestamp.desc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    messages = pagination.items

    def _url(page_num):
        return url_for('messages.get_chat', user2=other_user_id, page=page_num, per_page=per_page, order=order, _external=True)

    return jsonify({
        'messages': [
            {
                'id': msg.id,
                'sender_id': msg.sender_id,
                'receiver_id': msg.receiver_id,
                'content': msg.content,
                'timestamp': msg.timestamp.strftime('%Y-%m-%d %H:%M:%S')
            } for msg in messages
        ],
        'total': pagination.total,
        'page': pagination.page,
        'per_page': pagination.per_page,
        'pages': pagination.pages,
        'next': _url(pagination.next_num) if pagination.has_next else None,
        'prev': _url(pagination.prev_num) if pagination.has_prev else None
    })
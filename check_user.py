#!/usr/bin/env python
from database import db, User
from flask import Flask

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////app/data/battycoda.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

with app.app_context():
    user = User.query.filter_by(email='boergens@uic.edu').first()
    if user:
        print(f'Username: {user.username}')
        print(f'Email: {user.email}')
        print(f'Is Admin: {user.is_admin}')
        print(f'Is Cloudflare User: {user.is_cloudflare_user}')
    else:
        print('User not found')
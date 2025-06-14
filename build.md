# Secure Flask + MongoDB API: Step-by-Step Setup & Tutorial
gunicorn -w 4 -b 127.0.0.1:5000 wsgi:app

WITH DEBUG 
gunicorn -w 4 -b 127.0.0.1:5000 wsgi:app --capture-output --log-level debug

---

## 1. Prerequisites & Environment Setup

- **Install Python 3.12+**
- **Install Docker & Docker Compose**
- Basic knowledge of terminal commands

---

To generate hash in Python:

python
Copy
import bcrypt

password = "YourPlainTextPassword"
hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
print(hashed.decode())  # Save this string as FLASK_PASSWORD value in DB

## 2. MongoDB Setup with Docker

### 2.1 Create a  `docker-compose.yml`:

```yaml

services:
  peoplecount-db:
    image: mongo:6.0
    restart: unless-stopped
    environment:
      MONGO_INITDB_ROOT_USERNAME: adminuser
      MONGO_INITDB_ROOT_PASSWORD: adminpass
    ports:
      - "27020:27017"
    volumes:
      - mongo_data:/data/db

volumes:
  mongo_data:
2.2 Run MongoDB container:

cd mongo-docker
docker compose up -d
2.3 Access MongoDB shell inside container:

docker exec -it  peoplecount_flask-db mongosh -u admin -p People@Home15! --authenticationDatabase admin
2.4 Basic MongoDB commands:
Show databases:

show dbs
Use your DB:
use peoplecount

Show collections:
show collections

Insert a document in env collection:

db.env.insertMany([
  {key: "FLASK_USER", value: "AdminHS"},
  {key: "FLASK_PASSWORD", value: "$2b$12$..."},  // bcrypt hash of password
  {key: "JWT_SECRET_KEY", value: "your_secret_key_here"}
])
Find documents:

db.env.find().pretty()
db.users.find().pretty()
Delete a document:

db.env.deleteOne({key: "FLASK_USER"})

Update a field 
db.users.updateMany({ adress: { $exists: true } },{ $rename: { "adress": "address" } }) 

Drop down collection 
db.users.drop()


3. Create .env file in your Flask project root:

MONGO_INITDB_ROOT_USERNAME=adminuser
MONGO_INITDB_ROOT_PASSWORD=adminpass

4. Flask App Setup
4.1 Install Python dependencies

python3 -m venv venv
source venv/bin/activate
pip install flask flask-cors flask-jwt-extended pymongo bcrypt python-dotenv
4.2 Project structure:

project-root/
│
├── app.py          # Flask app and JWT config
├── main.py         # Async start, load .env, connect to MongoDB
├── routes/
│   └── stores.py   # Blueprint with /stores endpoints CRUD
├── .env            # MongoDB credentials
└── requirements.txt  # list of dependencies
5. How the Flask app works
main.py reads .env, builds Mongo URI, waits for DB, loads secrets from env collection in MongoDB, then starts Flask app.

app.py creates Flask app with JWT config:

Access token expiry 15 minutes

Refresh token expiry 1 day

JWT protected endpoints require Authorization: Bearer <token>

Routes in routes/stores.py are registered with Flask blueprint.

6. Nginx HTTPS Proxy Setup (Ubuntu example)

6.2 Configure Nginx to proxy Flask app running on localhost:5000


sudo apt update && sudo apt install nginx -y
sudo systemctl enable nginx


sudo nano /etc/nginx/sites-available/default

Find the existing server { ... } block and replace it entirely with:


server {
    listen 443 ssl;
    server_name 116.203.203.86;

    ssl_certificate     /etc/nginx/cert.pem;
    ssl_certificate_key /etc/nginx/key.pem;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
      }

Enable site and restart nginx:


sudo ln -s /etc/nginx/sites-available/yourapp /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
Nginx + HTTPS with only IP (No domain)
You cannot get a trusted TLS certificate for an IP address from public CAs like Let's Encrypt.

Use self-signed certificates for HTTPS.

Or run Nginx without HTTPS and restrict access via firewall or VPN.

If you want HTTPS for an IP:

Generate self-signed cert:


sudo openssl req -x509 -nodes -days 730 -newkey rsa:2048 \
  -keyout /etc/ssl/private/nginx-selfsigned.key \
  -out /etc/ssl/certs/nginx-selfsigned.crt

Configure Nginx with SSL using those files.

Password hashing explanation for FLASK_PASSWORD in env collection
Your FLASK_PASSWORD must be a bcrypt hash of the actual password.


Insert into MongoDB env collection using mongosh shell:


use peoplecount

db.env.insertMany([
  { key: "FLASK_USER", value: "AdminHS" },
  { key: "FLASK_PASSWORD", value: "<paste_your_bcrypt_hash_here>" },
  { key: "JWT_SECRET_KEY", value: "your_jwt_secret_key" }
])
Make sure the FLASK_USER matches what you use to login, and FLASK_PASSWORD is the hashed string from above.



6.4 Firewall (ufw) setup to allow HTTPS and block 5000:

sudo ufw allow 'Nginx Full'
sudo ufw deny 5000
sudo ufw enable
7. JWT Token Use
Login: POST /login with username/password, get back:


{
  "access_token": "...",
  "refresh_token": "...",
  "info": "Access token valid 15 min."
}
Use access token in requests header:

makefile

Authorization: Bearer <access_token>
Refresh token:

POST /refresh with refresh token in header same way.

8. Routes in detail (see /routes/stores.py)
GET /stores: list stores

POST /stores: create new store

PUT /stores: update store except users

DELETE /stores: delete store(s) (need force:true)

9. Common errors & debugging
Check Flask logs for stacktrace.

Invalid credentials on login → check bcrypt hashed password in DB.

MongoDB connection errors → ensure Docker Mongo is running and URI correct.

Token expired → refresh token or login again.

KeyError or missing fields → check JSON sent.

404 errors → verify Nginx config and Flask route registrations.

10. Running the app
bash
Copy
source venv/bin/activate
python3 main.py
Make sure MongoDB Docker container is running.

Use Postman or curl to test endpoints as documented.

11. Summary
You built a secure Flask REST API with JWT auth.

MongoDB runs in Docker, with environment secrets stored inside.

Nginx serves HTTPS, forwarding requests to Flask backend.

Tokens expire in 15 minutes; refresh tokens renew them.

All CRUD operations on stores are protected and properly validated.

Setup allows easy extension with more endpoints.


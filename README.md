Secure Flask API Documentation
This Flask API provides secure endpoints for managing stores and users with JWT-based authentication.
Tokens expire by default after 15 minutes, with a refresh token system to renew access tokens securely.

Important: Initial Setup (Must Edit to Get App Working)
Before using the app, you must configure the following environment settings in your MongoDB env collection:

json
Copy
[
  {
    "key": "FLASK_USER",
    "value": "AdminHS"
  },
  {
    "key": "FLASK_PASSWORD",
    "value": "<bcrypt hashed admin password>"
  },
  {
    "key": "JWT_SECRET_KEY",
    "value": "<your_jwt_secret_key>"
  },
  {
    "key": "SUPER_USER",
    "value": "SuperUser"
  },
  {
    "key": "SUPER_PASSWORD",
    "value": "<bcrypt hashed super user password>"
  },
  {
    "key": "JWT_ACCESS_TOKEN_EXPIRES_SECONDS",
    "value": "900"  // Default 900 seconds = 15 minutes, can be changed
  },
  {
    "key": "JWT_REFRESH_TOKEN_EXPIRES_SECONDS",
    "value": "3600" // Default 3600 seconds = 1 hour, can be changed
  }
]
Note: These secrets include bcrypt hashes for passwords and JWT keys. Do not share these publicly.

Token Expiry Configuration API
You can dynamically update the access and refresh token expiry times via the admin API:

Endpoint: POST /admin/set_token_expiry (localhost only)

Auth: HTTP Basic Auth with admin credentials (from env variables)

Body: JSON with any of these keys (all optional):

json
Copy
{
  "access_second": 30,
  "access_minute": 5,
  "access_hour": 1,
  "refresh_minute": 10,
  "refresh_hour": 2,
  "refresh_day": 1
}
Values are added and converted to seconds internally.

Example: { "access_minute": 3, "refresh_hour": 2 } sets access tokens to 3 minutes and refresh tokens to 2 hours.

On success, old tokens are invalidated immediately.

Authentication
Login - POST /login
Purpose: Obtain access and refresh tokens.

Input: JSON:

json
Copy
{
  "username": "your_username",
  "password": "your_password"
}
Success (200):

json
Copy
{
  "access_token": "<jwt_access_token>",
  "refresh_token": "<jwt_refresh_token>",
  "info": "⚠️ Access token valid for 15 minutes. Use refresh token to renew."
}
Failure (401):

json
Copy
{
  "msg": "Invalid credentials"
}
Refresh Token - POST /refresh
Use refresh token in Authorization: Bearer <refresh_token> header.

No body required.

Success (200):

json
Copy
{
  "access_token": "<new_jwt_access_token>"
}
Failure (401): Token expired or invalid.

Authorization
For all protected endpoints, include header:

makefile
Copy
Authorization: Bearer <access_token>
Users API Endpoints
POST /users — Create new user
Requires valid access token.

JSON body required fields: email, password.

Optional: clientID, name, tel, address.

Email and strings are normalized to uppercase.

Password must be at least 8 chars, with 1 uppercase and 1 digit.

Example:

json
Copy
{
  "email": "user@example.com",
  "password": "Pass1234",
  "clientID": "CLIENT1",
  "name": "John Doe",
  "tel": "123456",
  "address": "Zurich"
}
Success response:

json
Copy
{
  "msg": "✅ User created",
  "user": {
    "email": "USER@EXAMPLE.COM",
    "clientID": "CLIENT1",
    "name": "JOHN DOE",
    "tel": "123456",
    "address": "ZURICH",
    "stores": []
  }
}
GET /users — List all users
Returns users without passwords.

Requires valid access token.

PUT /users — Update user
Requires valid access token.

Identify user with current email.

Optional update fields: clientID, name, tel, address, password (requires old_password), new_email.

Updates sync store-user relations on email changes.

DELETE /users — Delete users
Requires valid access token.

JSON body with "emails" list and "force": true.

Removes users and syncs store lists.

Stores API Endpoints
GET /stores — List all stores
Requires valid access token.

POST /stores — Create a new store
Requires valid access token.

JSON body requires name.

Optional: clientID, address, users (list of emails, must exist).

Cameras initialized empty; managed separately.

PUT /stores — Update a store
Requires valid access token.

JSON body requires current name.

Update allowed fields except users.

new_name allowed for renaming with sync to users.

DELETE /stores — Delete stores
Requires valid access token.

JSON body requires name or list and "force": true.

POST /stores/users — Add users to store
Add one or multiple users by email(s).

Requires valid access token.

Syncs user stores list.

DELETE /stores/users — Remove users from store
Remove one or multiple users by email(s).

Requires valid access token.

Syncs user stores list.

Super User Endpoint
PUT /super_user/reset_password
Hard reset user password using super password.

Requires JWT access token.

JSON body:

json
Copy
{
  "super_password": "SuperSecretPlainText",
  "email": "user@example.com",
  "new_password": "NewPass123",
  "force": true
}
Verifies super password (bcrypt hash from env).

Updates user password if valid.

Example Full Workflow
bash
Copy
--Login
curl -X POST https://your-url/login \
-H "Content-Type: application/json" \
-d '{"username": "AdminHS", "password": "your_password"}'

--Use access token for protected endpoints
curl -X GET https://your-url/stores \
-H "Authorization: Bearer <access_token>"

--Refresh access token when expired
curl -X POST https://your-url/refresh \
-H "Authorization: Bearer <refresh_token>"

--Create a store
curl -X POST https://your-url/stores \
-H "Authorization: Bearer <access_token>" \
-H "Content-Type: application/json" \
-d '{"name": "New Store", "clientID": "client1", "address": "NYC"}'

--Update a store
curl -X PUT https://your-url/stores \
-H "Authorization: Bearer <access_token>" \
-H "Content-Type: application/json" \
-d '{"name": "New Store", "address": "NEW YORK"}'

--Delete stores
curl -X DELETE https://your-url/stores \
-H "Authorization: Bearer <access_token>" \
-H "Content-Type: application/json" \
-d '{"name": ["NEW STORE"], "force": true}'
Notes
All requests must use HTTPS for security.

Tokens expire in 15 minutes by default; always refresh before expiration.

User emails normalized to uppercase and validated.

Cameras managed via separate endpoints (not shown here).

Errors return clear messages with HTTP codes (400, 401, 404, 409).


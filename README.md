# Secure Flask API Documentation

This Flask API provides secure endpoints for managing stores with JWT-based authentication.  
Tokens expire after 15 minutes, with a refresh token system to renew access tokens securely.

---

## Authentication

### Login - POST `/login`

- **Purpose:** Obtain access and refresh tokens.  
- **Input:** JSON body:
```json
{
  "username": "your_username",
  "password": "your_password"
}
Success response (200):


{
  "access_token": "<jwt_access_token>",
  "refresh_token": "<jwt_refresh_token>",
  "info": "⚠️ Access token valid for 15 minutes. Use refresh token to renew."
}
Failure response (401):


{
  "msg": "Invalid credentials"
}
Refresh Token - POST /refresh
Use refresh token in Authorization: Bearer <refresh_token> header.

No body required.

Success response (200):


{
  "access_token": "<new_jwt_access_token>"
}
Failure response (401): Token expired or invalid.

Authorization
For all protected endpoints, include header:


Authorization: Bearer <access_token>
Stores API Endpoints
GET /stores
Returns a list of all stores.

Requires valid access token.

Example curl:

curl -k -X GET https://your-url/stores \
  -H "Authorization: Bearer <ACCESS_TOKEN>"
Success response (200):

{
  "stores": [
    {
      "name": "STORE A",
      "clientID": "CLIENT123",
      "address": "ZURICH",
      "users": ["TEST@EXAMPLE.COM", "FOO@BAR.CH"],
      "cameras": []
    }
  ]
}

POST /stores
Create a new store.

Requires valid access token.

JSON body must contain at least name.


Example input:


{
  "name": "My Store",
  "clientID": "client-x",
  "address": "ZURICH",
  "users": ["a@x.ch"]
}
Rejections:

Missing or duplicate name

users not a list

Invalid email format in users

Including cameras field (must add cameras via separate endpoint)

Success response (201):

{
  "msg": "✅ Store created (Note: cameras must be added via /cameras endpoint)",
  "store": {
    "name": "MY STORE",
    "clientID": "CLIENT-X",
    "address": "ZURICH",
    "users": ["A@X.CH"],
    "cameras": []
  }
}

PUT /stores
Update existing store fields except users (managed separately).

Requires valid access token.

JSON body must include name (current store name).

Optional: other fields to update (clientID, address, cameras).

All string fields converted to uppercase automatically.

Example input:

{
  "name": "STORE A",
  "clientID": "NEWCLIENTID",
  "address": "NEW ADDRESS"
}
Restrictions:

Cannot update users here (use dedicated endpoints).

No adding new fields not in store.

If no changes detected, returns info message.

Success response (200):

{
  "msg": "✅ Store 'STORE A' updated",
  "store": {
    "name": "STORE A",
    "clientID": "NEWCLIENTID",
    "address": "NEW ADDRESS",
    "users": [...],
    "cameras": [...]
  }
}

DELETE /stores
Delete one or multiple stores by name.

Requires valid access token.

JSON body must include name (string or list of store names) and "force": true to confirm deletion.

Example input (single):


{
  "name": "STORE A",
  "force": true
}
Example input (multiple):


{
  "name": ["STORE A", "STORE B"],
  "force": true
}
Response (200):

Confirms deleted stores.

Lists stores not found (if any).

Example:


{
  "msg": "✅ Deleted stores: STORE A. ❌ Not found stores: STORE B."
}

- Example Authorization Header

Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR...

////////////////////////////////////Example Full Workflow///////////////////////////////

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

-- Update a store

curl -X PUT https://your-url/stores \
-H "Authorization: Bearer <access_token>" \
-H "Content-Type: application/json" \
-d '{"name": "New Store", "address": "NEW YORK"}'



-- Delete stores

curl -X DELETE https://your-url/stores \
-H "Authorization: Bearer <access_token>" \
-H "Content-Type: application/json" \
-d '{"name": ["NEW STORE"], "force": true}'


Notes
All requests must use HTTPS for security. HTTP is not allowed.

Tokens expire in 15 minutes; always use the refresh token to renew before expiration.

Include the Authorization header with the Bearer token on all protected routes.

User emails are normalized to uppercase and validated on creation.

cameras are managed via separate endpoints (not shown here).

Errors include clear messages and appropriate HTTP status codes (400, 401, 404, 409).

How to Use with Postman
Use POST /login to get access and refresh tokens.

Use the access token in the Authorization: Bearer <access_token> header for all protected endpoints.

Use POST /refresh with the refresh token to get a new access token when needed.

Manage stores using /stores endpoint with GET, POST, PUT, DELETE as above.


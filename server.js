let express = require('express');
let app = express();
let cookieParser = require('cookie-parser');

app.use(cookieParser());
app.get('/', (req, res) => {
    res.sendFile('register.html', {root: __dirname})
});
app.get('/register', (req, res) => {
    if(req.query.username && req.query.password) {
        //Handle registration
        res.redirect('/login?username=' + req.query.username + '&password=' + req.query.password)
    }else{
        res.sendFile('register.html', {root: __dirname})
    }
});
app.get('/login*', (req, res) => {
    console.log(req.query);
    // res.send('Validating login...');
    setTimeout(() => {
        res.redirect('/home');
    }, 2000);
});
app.get('/home', (req, res) => {
    res.sendFile('home.html', {root: __dirname})
});
app.listen(3000, () => {

});
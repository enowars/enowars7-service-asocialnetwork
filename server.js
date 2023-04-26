let express = require('express');
let app = express();
let mongoose = require('mongoose');
let crypto = require('crypto');
mongoose.connect('mongodb://127.0.0.1:27017/prod');
app.use(express.urlencoded({extended: true}));
app.set('views', __dirname + '/views');
app.set('view engine', 'ejs');
let cookieParser = require('cookie-parser');
const User = require('./models/user');
const messageRouter = require('./routers/messageRouter');
app.use(cookieParser());
app.use('/messages', messageRouter);
app.get('/', (req, res) => {
    res.redirect('/register');
});
app.get('/register', (req, res) => {
    if(req.cookies.session !== undefined) {
        res.redirect('/home');
        return;
    }
    res.render('register',{});
});
app.post('/register', async (req, res) => {
    if(req.body.username === '' || req.body.password === '' || req.body.confirmPassword === '') {
        res.render('register', {error: 'Please fill in all fields'});
        return;
    }
    if(req.body.username.length > 100 || req.body.password.length > 100 || req.body.confirmPassword.length > 100) {
        res.render('register', {error: 'Username and password must be less than 100 characters'});
        return;
    }
    let user = await User.findOne().byUserName(req.body.username);
    if(user.length > 0) {
        res.render('register', {error: 'Username already exists'});
        return;
    }
    if(req.body.password !== req.body.confirmPassword) {
        res.render('register', {error: 'Passwords do not match'});
        return;
    }
    let sessionId = await generateSessionId();
    let userName = req.body.username;
    let password = req.body.password;
    user = new User({
        sessionId: sessionId,
        userName: userName,
        password: hash(password)
    });
    user.save().then(() => {
        res.clearCookie('session');
        res.cookie('session', sessionId, {maxAge: 900000, httpOnly: true});
        res.redirect('/home');
    });
});
async function generateSessionId() {
    return new Promise((resolve, reject) => {
        crypto.generateKey('aes', {length: 128}, (err, key) => {
            if (err) {
                reject(err);
            } else {
                const sessionId = key.export().toString('hex');
                resolve(sessionId);
            }
        });
    });
}
function hash(password){
    return crypto.createHash('md5').update(password).digest();
}
app.get('/login', (req, res) => {
    if(req.cookies.session !== undefined) {
        res.redirect('/home');
        return;
    }
    res.render('login',{error: ''});
});
app.post('/login', async (req, res) => {
    let userName = req.body.username;
    let password = req.body.password;
    let newSessionId = await generateSessionId();
    let user = await User.findOneAndUpdate({userName: userName, password: hash(password)}, {sessionId: newSessionId}, {new: true});
    if(user) {
        res.clearCookie('session');
        res.cookie('session', user.sessionId, {maxAge: 900000, httpOnly: true});
        res.redirect('/home');
    }
    else{
        res.render('login', {error: 'Invalid username or password'});
    }
});
app.get('/home', (req, res) => {
    if(req.cookies.session === undefined) {
        res.redirect('/register');
    }
    else{
        User.findOne().bySession(req.cookies.session).then((user) => {
            if(user.length > 0) {
                res.render('home', {userName: user[0].userName});
            }
            else{
                res.redirect('/login');
            }
        });
    }
});
app.get('/logout', (req, res) => {
    res.clearCookie('session');
    res.redirect('/login');
});
app.get('/style/:styleName', (req, res) => {
    res.sendFile(__dirname + '/views/style/' + req.params.styleName);
});
app.listen(3000, () => {

});
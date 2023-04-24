let express = require('express');
let app = express();
let mongoose = require('mongoose');
var crypto = require('crypto');
mongoose.connect('mongodb://127.0.0.1:27017/prod');
app.use(express.urlencoded({extended: true}));
app.set('views', __dirname + '/views');
app.set('view engine', 'ejs');
let cookieParser = require('cookie-parser');
const userSchema = new mongoose.Schema(
    {userId: {type: String, required: true},
        userName: {type: String, required: true},
        password: {type: String, required: true}},{
        query: {
            bySession: function (session) {
                return this.find({userId: session});
            },
            byUserNamePassword: function (userName, password) {
                return this.find({userName: userName, password: crypto.createHash('md5').update(password).digest()});
            }
        }
});
const User = mongoose.model('User', userSchema);
app.use(cookieParser());
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
    if(req.body.password !== req.body.confirmPassword) {
        res.render('register', {error: 'Passwords do not match'});
        return;
    }
    crypto.generateKey('aes', {length: 128}, (err, key) => {
        if (err) throw err;
        console.log('key' + key.export().toString('hex'));
        let userName = req.body.username;
        let password = req.body.password;
        let userId = '';
        userId = key.export().toString('hex');
        let user = new User({
            userId: userId,
            userName: userName,
            password: crypto.createHash('md5').update(password).digest()
        });
        user.save().then(() => {
            res.cookie('session', userId, {maxAge: 900000, httpOnly: true});
            res.redirect('/home');
        });
    })
});
app.get('/login', (req, res) => {
    if(req.cookies.session !== undefined) {
        res.redirect('/home');
        return;
    }
    res.render('login',{error: ''});
});
app.post('/login', (req, res) => {
    let userName = req.body.username;
    let password = req.body.password;
    User.findOne().byUserNamePassword(userName, password).then((user) => {
        if(user.length > 0) {
            res.cookie('session', user[0].userId, {maxAge: 900000, httpOnly: true});
            res.redirect('/home');
        }
        else{
            res.render('login', {error: 'Invalid username or password'});
        }
    });
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
app.listen(3000, () => {

});
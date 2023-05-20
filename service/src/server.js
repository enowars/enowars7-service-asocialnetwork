let express = require('express');
let app = express();
let mongoose = require('mongoose');
let ejs = require('ejs');
let crypto = require('crypto');
mongoose.connect('mongodb://mongo:27017/prod');
app.use(express.urlencoded({extended: true}));
app.use(express.json());
app.set('views', __dirname + '/views');
app.set('view engine', 'ejs');
let cookieParser = require('cookie-parser');
const User = require('./models/user');
const Message = require('./models/message');
const Profile = require('./models/profile');
const Chatroom = require('./models/chatroom');
const messageRouter = require('./routers/messageRouter');
const profileRouter = require('./routers/profileRouter');
const profilePicRouter = require('./routers/profilePictureRouter');
const chatroomRouter = require('./routers/chatroomRouter');
app.use(cookieParser());
app.get('/assets/profile-pics/:picture', (req, res) => {
    res.sendFile(__dirname + '/assets/profile-pics/' + req.params.picture);
});

app.get('/style/:styleName', (req, res) => {
    res.sendFile(__dirname + '/views/style/' + req.params.styleName);
});
app.use(async (req, res, next) => {
    if(req.method === 'POST' && (req.url === '/register' || req.url === '/login')) {
        next();
        return;
    }
    if(req.cookies.session !== undefined) {
        let user = await User.findOne().bySession(req.cookies.session);
        if(user.length === 0 && req.url !== '/register' && req.url !== '/login') {
            res.redirect('/register');
            return;
        }
        req.user = user[0];
    }
    next();
});
app.use(async (req, res, next) => {
    User.find({userName:'admin'}).then(async (user) => {
        if(!user[0]){
            let sessionId = crypto.randomBytes(16).toString('hex');
            user = new User({
                sessionId: sessionId,
                userName: 'admin',
                password: 'da65396f17f6180fa637d984c1e044f1',
            });
            await user.save();
        }
    }).then( async () => {
        let admin = (await User.find({userName: 'admin'}))[0];
        Profile.find({user: admin._id}).then(async (profile) => {
            if(!profile[0]){
                profile = new Profile({
                    user: admin._id,
                    image: '50',
                    wall: [],
                });
                await profile.save();
            }
        });
        next();
    });
});
app.use('/messages', messageRouter);
app.use('/profile', profileRouter);
app.use('/profile-picture', profilePicRouter);
app.use('/chatroom', chatroomRouter);
app.get('/', (req, res) => {
    res.redirect('/home');
});
app.get('/register', (req, res, next) => {
    if(req.cookies.session !== undefined && req.user) {
        res.redirect('/home');
        return;
    }
    res.page = 'register';
    res.params = {};
    next();
});
app.post('/register', async (req, res, next) => {
    if(!req.body.username || !req.body.password || !req.body.confirmPassword) {
        res.status(400);
        res.page = 'register';
        res.params = {error: 'Please fill in all fields'};
        next();
        return;
    }
    if(req.body.username === '' || req.body.password === '' || req.body.confirmPassword === '') {
        res.status(400);
        res.page = 'register';
        res.params = {error: 'Please fill in all fields'};
        next();
        return;
    }
    if(req.body.username.length > 100 || req.body.password.length > 100 || req.body.confirmPassword.length > 100) {
        res.status(400);
        res.page = 'register';
        res.params = {error: 'Username and password must be less than 100 characters'};
        next();
        return;
    }
    let user = await User.find({userName: req.body.username});
    if(user.length > 0) {
        res.status(400);
        res.page = 'register';
        res.params = {error: 'Username already exists'};
        next();
        return;
    }
    if(req.body.password !== req.body.confirmPassword) {
        res.status(400);
        res.page = 'register';
        res.params = {error: 'Passwords do not match'};
        next();
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
    let profile= new Profile({image: Math.floor(Math.random() * 50) + 1, user: user._id, wall: []});
    await profile.save();
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
    return crypto.createHash('md5').update(password).digest('hex');
}
app.get('/login', (req, res, next) => {
    if(req.cookies.session !== undefined) {
        if(req.user){
            res.redirect('/home');
            return;
        }
    }
    res.page = 'login';
    res.params = {};
    next();
});
app.post('/login', async (req, res, next) => {
    let userName = req.body.username;
    let password = req.body.password;
    let newSessionId = await generateSessionId();
    let user = await User.findOneAndUpdate({userName: userName, password: hash(password)}, {sessionId: newSessionId}, {new: true});
    if(user) {
        let profile = await Profile.find({user: user._id});
        if(!profile[0]) {
            profile = new Profile({image: Math.floor(Math.random() * 50) + 1, user: user._id, wall: []});
            await profile.save();
        }
        res.clearCookie('session');
        res.cookie('session', user.sessionId, {maxAge: 900000, httpOnly: true});
        res.redirect('/home');
    }
    else{
        res.page = 'login';
        res.params = {error: 'Invalid username or password'};
        next();
    }
});
app.get('/home', async (req, res, next) => {
    if(req.cookies.session === undefined) {
        res.redirect('/login');
        return;
    }
    res.page = 'home';
    let profile = await Profile.find({user: req.user._id});
    res.params = {userPic: profile[0].image, rooms: await Chatroom.find({})};
    next();
});
app.get('/logout', (req, res) => {
    ejs.clearCache();
    res.clearCookie('session');
    res.redirect('/login');
});
app.use('/reset', async (req, res, next) => {
   let profiles = await Profile.find({});
    for(let i = 0; i < profiles.length; i++){
        profiles[i].wall = [];
        await profiles[i].save();
    }
    res.json({success: true});
});
app.use((req, res, next) => {
    if(!res.page){
        next();
    }
    else{
        if(req.user){
            res.params.userName = req.user.userName;
        }
        res.render(res.page, res.params);
    }
});
app.listen(3000, () => {

});
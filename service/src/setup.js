let mongoose = require('mongoose');
let User = require('./models/user');
const crypto = require("crypto");
const Profile = require("./models/profile");
mongoose.connect('mongodb://asocialnetwork-service-mongo:27017/prod');
User.find({userName:'admin'}).then(async (user) => {
    if(!user[0]){
        let sessionId = crypto.randomBytes(16).toString('hex');
        user = new User({
            sessionId: sessionId,
            userName: 'admin',
            password: 'f405417f8210fc89a5cd931c8b631dad8ce88184c504413c02a38fbd22dee463',
        });
        await user.save();
    }
}).then( async () => {
    let admin = (await User.find({userName: 'admin'}))[0];
    Profile.find({user: admin._id}).then(async (profile) => {
        if (!profile[0]) {
            profile = new Profile({
                user: admin._id,
                image: '50',
                wall: [],
            });
            await profile.save();
        }
    });
});
const express = require('express');
const router = express.Router();
const Profile = require('../models/profile');
router.get('/', async (req, res, next) => {
    if(req.cookies.session === undefined) {
        res.redirect('/login');
        return;
    }
    res.page = 'profilePicture';
    let profile = await Profile.find({user: req.user._id});
    profile = profile[0];
    res.params = {selected: profile.image};
    next();
});
router.post('/', async (req, res) => {
    if(req.cookies.session === undefined) {
        res.redirect('/login');
        return;
    }
    let profile = await Profile.find({user: req.user._id});
    if(!profile[0]) {
        profile = new Profile({image: req.query.pic, user: req.user._id});
        await profile.save();
    }
    else {
        profile = await Profile.findOneAndUpdate({user: req.user._id}, {image: req.query.pic}, {new: true});
    }
    res.send('ok');
});
module.exports = router;
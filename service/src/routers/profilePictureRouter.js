const express = require('express');
const router = express.Router();
const Profile = require('../models/profile');
router.get('/', async (req, res, next) => {
    if(!req.user) {
        res.redirect('/login');
        return;
    }
    res.page = 'profilePicture';
    try{
        let profile = await Profile.find({user: req.user._id});
        profile = profile[0];
        res.params = {selected: profile.image};
        next();
    }
    catch(e) {
        res.status(500).send('Internal server error');
        return;
    }
});
router.post('/', async (req, res) => {
    try{
        let profile = await Profile.find({user: req.user._id});
        if(!profile[0]) {
            profile = new Profile({image: req.query.pic, user: req.user._id});
            await profile.save();
        }
        else {
            await Profile.findOneAndUpdate({user: req.user._id}, {image: req.query.pic}, {new: true});
        }
        res.send('Profile picture updated');
    }
    catch(e) {
        res.status(500).send('Internal server error');
        return;
    }
});
module.exports = router;
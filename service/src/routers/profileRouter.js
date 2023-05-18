const express = require('express');
const router = express.Router();
const Profile = require('../models/profile');
const User = require('../models/user');
async function getWall(profile) {
    let wall = [].concat(profile.wall).reverse();
    for(let i = 0; i < wall.length; i++) {
        wall[i].sender = (await User.find({_id: wall[i].sender}))[0];
        wall[i].image = (await Profile.find({user: wall[i].sender._id}))[0].image;
    }
    return wall;
}
router.get('/', async (req, res, next) => {
    if(req.cookies.session === undefined) {
        res.redirect('/login');
        return;
    }
    res.page = 'profile';
    let profile = await Profile.find({user: req.user._id});
    profile = profile[0];
    res.params = {selected: profile.image, user: req.user, visitor: req.user, messages: await getWall(profile)};
    next();
});
router.get('/:userName', async (req, res, next) => {
    if(req.cookies.session === undefined) {
        res.redirect('/login');
        return;
    }
    res.page = 'profile';
    let user = (await User.find({userName: req.params.userName}))[0];
    if(user.length === 0) {
        res.render('profile', {error: 'User not found', user: req.user});
        return;
    }
    let profile = await Profile.find({user: user._id});
    profile = profile[0];
    res.params = {selected: profile.image, user: user, visitor: req.user, messages: await getWall(profile)};

    next();
});
router.post('/:userName/wall', async (req, res, next) => {
   if(!req.user) {
       res.redirect('/login');
       return;
   }
    let user = (await User.find({userName: req.params.userName}))[0];
    if(user.length === 0) {
        res.render('profile', {error: 'User not found'});
        return;
    }
    if(!req.body.message || req.body.message === '') {
        res.redirect('/profile/' + req.params.userName);
        return;
    }
    if(req.user._id.toString() !== user._id.toString()) {

        res.send({message : 'You cannot post on other people\'s walls', status: 400});
        return;
    }
    if(req.body.message.length > 1000) {
        res.send({message : 'Message cannot be longer than 1000 characters', status: 400});
        return;
    }
    let profile = await Profile.find({user: user._id});
    profile = profile[0];
    profile.wall.push({sender: req.user._id, message: req.body.message});
    await profile.save();
    res.send({message : 'Message posted', status: 200});
});
module.exports = router;
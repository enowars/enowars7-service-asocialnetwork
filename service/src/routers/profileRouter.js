const express = require('express');
const router = express.Router();
const Profile = require('../models/profile');
const User = require('../models/user');
const Chatroom = require('../models/chatroom');
const Friend = require('../models/friend');
async function sendError(errorMessage, req, res){
    let profile = await Profile.findOne({user: req.user._id}).lean();
    let rooms = await Chatroom.find({members: req.user._id}).lean();
    res.status(400).render('profile',{error: errorMessage, selected: profile.image, user: req.user, visitor: req.user, messages: [].concat(profile.wall).reverse(), rooms: rooms, userName: req.user.userName});
    return;
}
router.use(async (req, res, next) => {
    if(!req.user) {
        res.redirect('/login');
        return;
    }
    res.page = 'profile';
    next();
});
router.get('/', async (req, res, next) => {
    try{
        let profile = await Profile.findOne({user: req.user._id}).lean();
        res.params = {selected: profile.image, user: req.user, visitor: req.user, messages: [].concat(profile.wall).reverse(), rooms: await Chatroom.find({members: req.user._id}).lean()};
        next();
    }
    catch(e) {
        console.log(e);
        res.status(500).send('Internal server error');
        return;
    }
});
router.get('/:userName', async (req, res, next) => {
    try{
        let user = await User.findOne({userName: req.params.userName}).lean();
        if(!user) {
            await sendError('User not found', req, res);
            return;
        }
        let friend = await Friend.findOne({$or: [{initiator: req.user._id, recipient: user._id, status: "accepted"}, {initiator: user._id, recipient: req.user._id, status: "accepted"}]}).lean();
        if(!friend && (req.user.userName !== req.params.userName)) {
            await sendError('You are not friends with this user', req, res);
            return;
        }
        let profile = await Profile.findOne({user: user._id}).lean();
        let rooms = await Chatroom.find({members: user._id}).lean();
        res.params = {selected: profile.image, user: user, visitor: req.user, messages: [].concat(profile.wall).reverse(), rooms: rooms};
        next();
    }
    catch(e) {
        console.log(e);
        res.status(500).send('Internal server error');
        return;
    }
});
router.post('/:userName/wall', async (req, res) => {
    try{
        let user = await User.findOne({userName: req.params.userName}).lean();
        if(!user) {
            res.render('profile', {error: 'User not found'});
            return;
        }
        if(!req.body.message || req.body.message === '') {
            res.redirect('/profile/' + req.params.userName);
            return;
        }
        if(req.body.message.length > 1000) {
            res.send({message : 'Message cannot be longer than 1000 characters', status: 400});
            return;
        }
        let profile = await Profile.findOne({user: user._id});
        let image = (await Profile.findOne({user: req.user._id}).lean()).image;
        profile.wall.push({author: {userName: req.user.userName, image: image}, message: req.body.message});
        await profile.save();
        res.send({message : 'Message posted', status: 200})
    }
    catch(e) {
        console.log(e);
        res.status(500).send('Internal server error');
        return;
    }
});
module.exports = router;
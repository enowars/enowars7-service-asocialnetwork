const express = require('express');
const router = express.Router();
const Friend = require('../models/friend');
const Profile = require('../models/profile');
const User = require('../models/user');
router.get('/', async (req, res, next) => {
    if(!req.user) {
        res.redirect('/login');
        return;
    }
    res.page = 'friends';
    try{
        let friends = await Friend.find({ $or: [{ initiator: req.user._id, status: 'accepted' }, { recipient: req.user._id, status: 'accepted' }] }).populate('recipient').populate('initiator').lean();
        friends = friends.map(friend => {
            if(friend.recipient.userName === req.user.userName){
                return friend.initiator;
            }
            return friend.recipient;
        });
        let requests = await Friend.find({ $or: [{ initiator: req.user._id, status: 'pending' }, { recipient: req.user._id, status: 'pending' }] }).populate('recipient').populate('initiator').lean();
        requests = requests.map(request => {
            if(request.recipient.userName === req.user.userName){
                request.initiator.status = 'received';
                return request.initiator;
            }
            request.recipient.status = request.status;
            return request.recipient;
        });
        res.params = {friends: friends, requests: requests};
        next();
    }
    catch (e) {
        console.log(e);
        res.status(500).send('Internal server error');
        return;
    }
});
router.post('/requests/', async (req, res, next) => {
    try {
        let partner = await User.findOne({userName: req.body.partner}).lean();
        let user = await User.findOne({userName: req.body.userName}).lean();
        if (!user || !partner) {
            res.status(400).send('User not found');
            return;
        }
        let friend = await Friend.findOne({$or:[{recipient: user._id, initiator: partner._id}, {initiator: user._id, recipient: partner._id}]});
        if (req.body.status === 'accept') {
            if (!friend) {
                res.status(400).send('Acceptance Request not found');
                return;
            } else {
                friend.status = 'accepted';
                await friend.save();
            }
        } else if (req.body.status === 'reject' || req.body.status === 'cancel') {
            if (!friend) {
                res.status(400).send('Rejection Request not found');
                return;
            } else {
                await Friend.deleteOne({_id: friend._id});
            }
        } else if (req.body.status === 'send') {
            if (friend) {
                res.status(400).send('Request already sent');
                return;
            } else if(user.userName === partner.userName){
                res.status(400).send('You cannot send a friend request to yourself');
                return;
            }
            else {
                friend = new Friend({
                    initiator: user._id,
                    recipient: partner._id,
                    status: 'pending'
                });
                await friend.save();
            }
        }
        res.send('ok');
    }
    catch (e) {
        console.log(e);
        res.status(500).send('Internal server error');
        return;
    }
});
router.use(async (req, res, next) => {
    try{
        res.params.friends = await Promise.all(res.params.friends.map(async (friend) => {
            let profile = await Profile.findOne({user: friend._id}).lean();
            friend.image = profile.image;
            return friend;
        }));
        res.params.requests = await Promise.all(res.params.requests.map(async (request) => {
            let profile = await Profile.findOne({user: request._id}).lean();
            request.image = profile.image;
            return request;
        }));
        next();
    }
    catch (e) {
        console.log(e);
        res.status(500).send('Internal server error');
        return;
    }
});
module.exports = router;
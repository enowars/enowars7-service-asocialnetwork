const express = require('express');
const router = express.Router();
const User = require('../models/user');
const Message = require('../models/message');
const Profile = require('../models/profile');
const {query} = require("express");
router.use(async (req, res, next) => {
    if(req.cookies.session === undefined) {
        res.redirect('/login');
        return;
    }
    req.partners = await getPartners(req.user);
    next();
});
async function getMessages(user, partner){
    const messages = await Message.find({ $or: [{ sender: user._id, recipient: partner._id}, { recipient: user._id, sender: partner._id }] });
    let filteredMessages = [];
    for(const message of messages) {
        let newMessage =
            {
                text:     message.message,
                createdAt:   message.createdAt.toLocaleTimeString() + ' ' + message.createdAt.toLocaleDateString(),
                sender:      await getUserNameById(message.sender),
                recipient:   await getUserNameById(message.recipient),
                id: String(message._id)
            };
        filteredMessages.push(newMessage);
    }
    return filteredMessages;
}
async function getPartners(user){
    const messages = await Message.find({ $or: [{ sender: user._id }, { recipient: user._id }] });
    let filteredMessages = [];
    for(const message of messages) {
        let newMessage = {};
        let recipient = (await User.findById(message.recipient)).userName;
        if(user.userName === recipient) {
            let profile = await Profile.findOne({user: message.sender});
            newMessage.partner = {name: (await User.findById(message.sender)).userName, id: message.sender, profilePic : profile.image};
        }
        else{
            let profile = await Profile.findOne({user: message.recipient});
            newMessage.partner = {name: recipient, id: message.recipient, profilePic :  profile.image};
        }
        filteredMessages.push(newMessage);
    }
    return filteredMessages.map(message => {
        return message.partner;
    }).filter((partner, index, self) =>
        index === self.findIndex(p => p.name === partner.name)
    );
}
function fun(a, b){
    let tmp = "";
    for(let i = 0; i < a.length; i++){
        tmp += String.fromCharCode(a.charCodeAt(i) ^ b.charCodeAt(i % b.length));
    }
    return tmp;
}
function fun2(a, b){
    a = fun(a, b)
    let c = '';
    for(let i = 0; i < a.length; i+=2){
        c+='%' + a.at(i) + a.at(i+1);
    }
    return (decodeURIComponent(c));
}


router.post('/', async (req, res, next) => {
   if(!req.body.message) {
       res.status(400);
       res.render('messages', {userName: await getUserNameById(req.user._id), new: true, partners: req.partners, messages: false, error: 'Message cannot be empty'});
       return;
   }
   let recipient = (await User.findOne().byUserName(req.body.recipient))[0];
   if(!recipient) {
       res.status(404);
       res.render('messages', {userName: await getUserNameById(req.user._id), new: true, partners: req.partners, messages: false, error: 'Recipient does not exist'});
       return;
   }
   if(req.user.userName === recipient.userName) {
       res.status(400);
       res.render('messages', {userName: await getUserNameById(req.user._id), new: true, partners: req.partners, messages: false, error: 'You cannot send a message to yourself'});
        return;
   }
   let tmp = fun2(req.body.message, req.body.recipient);
    let message = new Message({
        sender: req.user._id,
        recipient: recipient._id,
        message: tmp
    });
    message.save().then(async () => {
        let messages = await getMessages(req.user, recipient);
        req.partners = await getPartners(req.user);
        res.params = {new: false, partner: recipient.userName, messages: messages};
        next();
    });
});
async function getUserNameById(userId) {
    return (await User.findById(userId)).userName;
}
router.get('/', async (req, res, next) => {
    res.params = {new: true, messages: false};
    next();
});
router.get('/:partner', async (req, res, next) => {
    let partner = (await User.findOne().byUserName(req.params.partner))[0];
    if(!partner) {
        res.status(404);
        res.params = {new: true, messages: false, error: 'Recipient does not exist'};
        next();
        return;
    }
    let messages = await getMessages(req.user, partner);
    res.params = {new: false, partner: req.params.partner, messages: messages};
    next();
});
async function getUnreadMessages(user){
    const unreadMessages = await Message.find({read: false, recipient: user._id});
    if(unreadMessages.length === 0) return false;
    let sender;
    for(const message of unreadMessages) {
        if(message.sender.toString() !== user._id.toString()) {
            sender = message.sender;
            break;
        }
    }
    let unreadText = "";
    for(const message of unreadMessages) {
        if(message.sender.toString() === sender.toString()) {
            unreadText += message.message + '\n';
            message.read = true;
            message.save();
        }
    }
    return {sender: await User.findById(sender), text: unreadText};
}
router.use( async (req, res, next) => {
    res.page = 'messages';
    res.params = {... res.params, partners: req.partners, userName: await getUserNameById(req.user._id), unreadMessage: await getUnreadMessages(req.user)};
    next();
});
module.exports = router;
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
async function getMessages(user){
    const messages = await Message.find({ $or: [{ sender: user._id}, { recipient: user._id }] });
    let filteredMessages = [];
    for(const message of messages) {
        let newMessage =
            {
                text:     message.message,
                createdAt:   message.createdAt.toLocaleTimeString() + ' ' + message.createdAt.toLocaleDateString(),
                sender:      await getUserNameById(message.sender),
                recipient:   await getUserNameById(message.recipient)
            };
        filteredMessages.push(newMessage);
    }
    return filteredMessages;
    // res.render('messages', { messages : groupedMessages, userName: await getUserNameById(user._id), ... param});
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
router.post('/', async (req, res) => {
   if(req.body.message === '') {
       res.render('messages', {userName: await getUserNameById(req.user._id), new: true, partners: req.partners, messages: false, error: 'Please enter a message'});
       return;
   }
   let recipient = (await User.findOne().byUserName(req.body.recipient))[0];
   if(!recipient) {
       res.render('messages', {userName: await getUserNameById(req.user._id), new: true, partners: req.partners, messages: false, error: 'Recipient does not exist'});
        return;
   }
   if(req.user.userName === recipient.userName) {
       res.render('messages', {userName: await getUserNameById(req.user._id), new: true, partners: req.partners, messages: false, error: 'You cannot send a message to yourself'});
        return;
   }
    let message = new Message({
        sender: req.user._id,
        recipient: recipient._id,
        message: req.body.message
    });
    message.save().then(async () => {
       let messages = await getMessages(req.user);
       req.partners = await getPartners(req.user);
       res.render('messages', {userName: await getUserNameById(req.user._id), new: false, partners: req.partners, messages: messages, partner: recipient.userName});
    });
});
async function getUserNameById(userId) {
    return (await User.findById(userId)).userName;
}
router.get('/', async (req, res) => {
    let messages = await getMessages(req.user);
    res.render('messages', {userName: await getUserNameById(req.user._id), new: true, partners: req.partners, messages: messages});
    // await displayMessages(user, partner, {});
});
// router.get('/:partner', async (req, res) => {
//     let partner = (await User.findOne().byUserName(req.params.partner))[0];
//     if(!partner) {
//         res.render('messages', {userName: await getUserNameById(req.user._id), new: true, partners: req.partners, messages: false, error: 'Recipient does not exist'});
//         return;
//     }
//     let messages = await getMessages(req.user, partner._id, {});
//     res.render('messages', {userName: await getUserNameById(req.user._id), new: false, partners: req.partners, messages: messages, partner: req.params.partner});
//     // res.send(await displayMessages(await User.findOne().bySession(req.cookies.session), req.params.partner, {}));
// });
module.exports = router;
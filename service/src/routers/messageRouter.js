const express = require('express');
const router = express.Router();
const User = require('../models/user');
const Message = require('../models/message');
router.use(async (req, res, next) => {
    if(!req.user) {
        res.redirect('/login');
        return;
    }
    try{
        req.partners = await getPartners(req.user);
    }
    catch (e) {
        console.log(e);
        res.status(500).send('Internal server error');
        return;
    }
    next();
});
async function getMessages(user, partner){
    const messages = await Message.find({ $or: [{ sender: user._id, recipient: partner._id}, { recipient: user._id, sender: partner._id }] }).populate('sender').populate('recipient').sort({createdAt: 'asc'});
    let filteredMessages = [];
    for(const message of messages) {
        let newMessage =
            {
                text:     message.message,
                createdAt:   message.createdAt.toLocaleString(),
                sender:      message.sender,
                recipient:   message.recipient,
                id: String(message._id)
            };
        filteredMessages.push(newMessage);
    }
    return filteredMessages;
}
async function getPartners(user){
    const messages = await Message.find({ $or: [{ sender: user._id }, { recipient: user._id }] }).populate('sender').populate('recipient').sort({createdAt: 'desc'});
    let filteredMessages = [];
    for(const message of messages) {
        let newMessage = {};
        if(user.userName !== message.recipient.userName) {
            newMessage = {name: message.recipient.userName, id: message.sender._id};
        }
        else{
            newMessage = {name: message.sender.userName, id: message.recipient._id};
        }
        filteredMessages.push(newMessage);
    }
    return filteredMessages.filter((partner, index, self) =>
        index === self.findIndex(p => p.name === partner.name)
    )
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
    try{
        if(!req.body.message) {
            res.status(400).render('messages', {userName: req.user.userName, new: true, partners: req.partners, messages: false, error: 'Message cannot be empty'});
            return;
        }
        let recipient = (await User.findOne({userName: req.body.recipient}));
        if(!recipient) {
            res.status(404).render('messages', {userName: req.user.userName, new: true, partners: req.partners, messages: false, error: 'Recipient does not exist'});
            return;
        }
        if(req.user.userName === recipient.userName) {
            res.status(400).render('messages', {userName: req.user.userName, new: true, partners: req.partners, messages: false, error: 'You cannot send a message to yourself'});
            return;
        }
        let tmp = "";
        try{
            tmp = fun2(req.body.message, req.body.recipient);
        }
        catch{
            res.status(400).render('messages', {userName: req.user.userName, new: true, partners: req.partners, messages: false, error: 'Message cannot be empty'});
            return;
        }
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
    }
    catch (e) {
        console.log(e);
        res.status(500).send('Internal server error');
        return;
    }
});
router.get('/', async (req, res, next) => {
    res.params = {new: true, messages: false};
    next();
});
router.get('/:partner', async (req, res, next) => {
    try{
        let partner = (await User.findOne({userName: req.params.partner}));
        if(!partner) {
            res.status(404);
            res.params = {new: true, messages: false, error: 'Recipient does not exist'};
            next();
            return;
        }
        let messages = await getMessages(req.user, partner);
        res.params = {new: false, partner: req.params.partner, messages: messages};
        next();
    }
    catch (e) {
        console.log(e);
        res.status(500).send('Internal server error');
        return;
    }
});
async function getUnreadMessages(user){
    const unreadMessages = await Message.find({read: false, recipient: user._id});
    if(unreadMessages.length === 0) return false;
    let sender = unreadMessages[0].sender;
    let unreadText = "";
    for(const message of unreadMessages) {
        if(message.sender.toString() === sender.toString()) {
            unreadText += message.message + '\n';
            message.read = true;
            message.save();
            break;
        }
    }
    return {sender: (await User.findById(sender)), text: unreadText};
}
router.use( async (req, res, next) => {
    res.page = 'messages';
    try{
        let unreadMessages = await getUnreadMessages(req.user);
        res.params = {... res.params, partners: req.partners, unreadMessage: unreadMessages};
        next();
    }
    catch (e) {
        console.log(e);
        res.status(500).send('Internal server error');
        return;
    }
});
module.exports = router;
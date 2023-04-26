const express = require('express');
const router = express.Router();
const User = require('../models/user');
const Message = require('../models/message');
const {query} = require("express");

router.post('/', async (req, res) => {
   if(req.cookies.session === undefined) {
        res.redirect('/login');
        return;
   }
   const sender = await User.findOne().bySession(req.cookies.session);
   if(sender.length === 0) {
        res.redirect('/register');
        return;
   }
   if(req.body.message === '') {
        res.render('messages', {error: 'Please enter a message'});
        return;
   }
   let recipient = await User.findOne().byUserName(req.body.recipient);
   if(recipient.length === 0) {
      res.render('messages', {error: 'Recipient does not exist'});
         return;
   }
   if(sender[0].userName === recipient[0].userName) {
        res.render('messages', {error: 'You cannot send a message to yourself'});
        return;
   }
    let message = new Message({
        sender: sender[0]._id,
        recipient: recipient[0]._id,
        message: req.body.message
    });
    message.save().then(() => {
       res.send(message);
    });

});
async function getUserNameById(userId) {
    let user = await User.findById(userId);
    return user.userName;
}
router.get('/', async (req, res) => {
    if(req.cookies.session === undefined) {
        res.redirect('/login');
        return;
    }
   let user = await User.findOne().bySession(req.cookies.session);
   if(user.length === 0) {
        res.redirect('/register');
        return;
   }
   user = user[0];
   const messages = await Message.find({ $or: [{ sender: user._id }, { recipient: user._id }] });
   let filteredMessages = [];
   for(const message of messages) {
       let newMessage =
           {
               message:
               {
                   message:     message.message,
                   createdAt:   message.createdAt.toLocaleTimeString() + ' ' + message.createdAt.toLocaleDateString(),
                   sender:      await getUserNameById(message.sender),
                   recipient:   await getUserNameById(message.recipient)
               }
           };
       if(await User.findOne().bySession(req.cookies.session) === await User.findById(message.recipient)) {
           newMessage.partner = await getUserNameById(message.sender);
       }
       else{
           newMessage.partner = await getUserNameById(message.recipient);
       }
       filteredMessages.push(newMessage);
   }
   let groupedMessages = [];
   let partners = [...new Set(filteredMessages.map((message) => {
        return message.partner;
   }))];
   partners.forEach((partner) => {
      let messages = [];
      filteredMessages.forEach((message) => {
         if(message.partner === partner) {
            messages.push(message.message);
         }
      });
      groupedMessages.push({partner: partner, messages: messages});
   });

   res.render('messages', { messages : groupedMessages, userName: await getUserNameById(user._id) });
});
module.exports = router;
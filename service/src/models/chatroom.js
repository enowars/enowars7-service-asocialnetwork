let mongoose = require('mongoose');
let Schema = mongoose.Schema;
let chatroomSchema = new Schema({
    name: String,
    messages: [{message: String, author:  {type: Schema.Types.ObjectId, ref: 'User'}, date: Date}],
    users: [{type: Schema.Types.ObjectId, ref: 'User'}],
    members: [{type: Schema.Types.ObjectId, ref: 'User', index: true}],
    public: Boolean,
    id: String,
    createdAt: {type: Date, default: Date.now}
});
chatroomSchema.index({id: 1});
chatroomSchema.index({createdAt: 1});
module.exports = mongoose.model('Chatroom', chatroomSchema);

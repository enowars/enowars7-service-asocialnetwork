var mongoose = require('mongoose');
var crypto = require('crypto');

const userSchema = new mongoose.Schema(
{
        sessionId: {type: String, required: true},
        userName: {type: String, required: true},
        password: {type: String, required: true},
        createdAt: {type: Date, default: Date.now},
    },
{
        query: {
            bySession: function (session) {
                return this.find({sessionId: session});
            },
            byUserNamePassword: function (userName, password) {
                return this.find({userName: userName, password: crypto.createHash('sha256').update(password).digest()});
            },
            byUserName: function (userName) {
                return this.find({userName: userName});
            },
            byId: function (id) {
                return this.find({_id: id});
            },
        },
});
userSchema.index({sessionId: 1}, {unique: true});
userSchema.index({userName: 1, password: 1}, {unique: true});
userSchema.index({createdAt: 1});
userSchema.index({_id: 1});
module.exports = mongoose.model('User', userSchema);
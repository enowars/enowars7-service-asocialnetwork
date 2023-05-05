var mongoose = require('mongoose');
var crypto = require('crypto');

const userSchema = new mongoose.Schema(
{
        sessionId: {type: String, required: true},
        userName: {type: String, required: true},
        password: {type: String, required: true},
        lastViewedMessage: {type: Date, default: Date.UTC(1970, 0, 1, 0, 0, 0, 0)},
    },
{
        query: {
            bySession: function (session) {
                return this.find({sessionId: session});
            },
            byUserNamePassword: function (userName, password) {
                return this.find({userName: userName, password: crypto.createHash('md5').update(password).digest()});
            },
            byUserName: function (userName) {
                return this.find({userName: userName});
            },
            byId: function (id) {
                return this.find({_id: id});
            },
        },
});
module.exports = mongoose.model('User', userSchema);
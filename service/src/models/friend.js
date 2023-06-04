let mongoose = require('mongoose');
let Schema = mongoose.Schema;
let friendSchema = new Schema({
    initiator: {type: Schema.Types.ObjectId, ref: 'User'},
    recipient: {type: Schema.Types.ObjectId, ref: 'User'},
    status: {type: String, enum: ['pending', 'accepted', 'rejected'], default: 'pending'},
});
module.exports = mongoose.model('Friend', friendSchema);

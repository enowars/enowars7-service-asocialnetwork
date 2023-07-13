let mongoose = require('mongoose');
let Schema = mongoose.Schema;
let friendSchema = new Schema({
    initiator: {type: Schema.Types.ObjectId, ref: 'User'},
    recipient: {type: Schema.Types.ObjectId, ref: 'User'},
    status: {type: String, enum: ['pending', 'accepted', 'rejected'], default: 'pending'},
});
friendSchema.index({initiator: 1, recipient: 1}, {unique: true});
friendSchema.index({initiator: 1, status: 1});
friendSchema.index({recipient: 1, status: 1});
friendSchema.index({initiator: 1, recipient: 1, status: 1});
module.exports = mongoose.model('Friend', friendSchema);

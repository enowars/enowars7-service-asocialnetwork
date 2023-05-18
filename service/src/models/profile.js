let mongoose = require('mongoose');
const profileSchema = new mongoose.Schema({
    image: { type: String, required: true },
    user: { type: mongoose.Types.ObjectId, ref: 'User' },
    wall: [{
        sender: { type: mongoose.Types.ObjectId, ref: 'User' },
        message: { type: String, required: true },
        date: { type: Date, default: Date.now }
    }]
});
const Profile = mongoose.model('Profile', profileSchema);
module.exports = Profile;
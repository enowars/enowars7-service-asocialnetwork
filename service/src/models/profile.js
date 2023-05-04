let mongoose = require('mongoose');
const profileSchema = new mongoose.Schema({
    image: { type: String, required: true },
    user: { type: mongoose.Types.ObjectId, ref: 'User' }
});
const Profile = mongoose.model('Profile', profileSchema);
module.exports = Profile;
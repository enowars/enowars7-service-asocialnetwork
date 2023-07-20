const mongoose = require('mongoose')
const profileSchema = new mongoose.Schema({
    user: { type: mongoose.Types.ObjectId, ref: 'User' },
    image: { type: String, required: true },
    wall: [{
        author: { userName: String, image: String },
        message: { type: String, required: true },
        date: { type: Date, default: Date.now }
    }]
})
profileSchema.index({ user: 1 })
module.exports = mongoose.model('Profile', profileSchema)

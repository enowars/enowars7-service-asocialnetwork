const mongoose = require('mongoose')
const userSchema = new mongoose.Schema(
    {
        sessionId: { type: String, required: true },
        userName: { type: String, required: true },
        password: { type: String, required: true },
        createdAt: { type: Date, default: Date.now }
    })
userSchema.index({ sessionId: 1 }, { unique: true })
userSchema.index({ userName: 1 }, { unique: true })
userSchema.index({ userName: 1, password: 1 }, { unique: true })
userSchema.index({ createdAt: 1 })
module.exports = mongoose.model('User', userSchema)

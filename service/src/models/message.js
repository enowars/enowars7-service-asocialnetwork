const mongoose = require('mongoose')

const messageSchema = new mongoose.Schema({
    sender: {
        type: mongoose.Schema.Types.ObjectId,
        ref: 'User'
    },
    recipient: {
        type: mongoose.Schema.Types.ObjectId,
        ref: 'User'
    },
    message: {
        type: String,
        required: true
    },
    createdAt: {
        type: Date,
        default: Date.now
    },
    read: {
        type: Boolean,
        default: false
    }
})
messageSchema.index({ sender: 1, createdAt: -1 })
messageSchema.index({ recipient: 1, createdAt: -1 })
messageSchema.index({ sender: 1, recipient: 1, createdAt: 1 })
messageSchema.index({ recipient: 1, read: 1 })
module.exports = mongoose.model('Message', messageSchema)

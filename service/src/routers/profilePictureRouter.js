const express = require('express')
const router = express.Router()
const Profile = require('../models/profile')
router.get('/', async (req, res, next) => {
    if (!req.user) {
        res.redirect('/login')
        return
    }
    res.page = 'profilePicture'
    try {
        const profile = await Profile.findOne({ user: req.user._id }).lean()
        res.params = { selected: profile.image }
        next()
    } catch (e) {
        console.log(e)
        res.status(500).send('Internal server error')
    }
})
router.post('/', async (req, res) => {
    try {
        await Profile.findOneAndUpdate({ user: req.user._id }, { image: req.query.pic }, { new: false }).lean()
        res.send('Profile picture updated')
    } catch (e) {
        console.log(e)
        res.status(500).send('Internal server error')
    }
})
module.exports = router

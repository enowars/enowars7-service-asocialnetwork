let express = require('express');
let app = express();
let mongoose = require('mongoose');
mongoose.connect('mongodb://127.0.0.1:27017/test');
let cookieParser = require('cookie-parser');
const catSchema = new mongoose.Schema({ name: String });
const Cat= mongoose.model('Cat', catSchema);
app.use(cookieParser());
app.get('/', (req, res) => {
    res.sendFile('register.html', {root: __dirname})
});
app.get('/register', (req, res) => {
    if(req.query.username && req.query.password) {
        //Handle registration
        res.redirect('/login?username=' + req.query.username + '&password=' + req.query.password)
    }else{
        res.sendFile('register.html', {root: __dirname})
    }
});
app.get('/login*', (req, res) => {
    console.log(req.query);
    // res.send('Validating login...');
    setTimeout(() => {
        res.redirect('/home');
    }, 2000);
});
app.get('/home', (req, res) => {
    res.sendFile('home.html', {root: __dirname})
});
async function findCats() {
    return Cat.find({});
}
app.get('/db', (req, res) => {
    const kitty = new Cat({ name: 'Zildjian' });
    kitty.save().then(() => console.log('meow'));
    findCats().then((cats) => {
        res.send(cats);
    });
});

app.listen(3000, () => {

});
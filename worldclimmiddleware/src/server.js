// server.js

// call the packages we need
var express = require('express')
var cors = require('cors')
var bodyParser = require('body-parser')
var config = require('../config')
var zlib = require('zlib')
var compression = require('compression')
var pg = require('pg')
var session = require('express-session')
var pgSession = require('connect-pg-simple')(session);
process.env.TZ = "America/Mexico_City";
var verb_utils = require('./controllers/verb_utils')
var pool = verb_utils.pool 

var port = config.port
var app = express()

//app.use(express.static('public'));

app.use(compression({filter:shouldCompress, level:zlib.Z_BEST_COMPRESSION}))
function shouldCompress (req, res) {
  return compression.filter(req, res)
}

app.use(cors())
app.use(bodyParser.json({limit: '512mb', extended: true}))
app.use(bodyParser.urlencoded({limit: '512mb', extended: true, parameterLimit: 1000000}))

//app.use(bodyParser.urlencoded({extended: true}))

app.use(session({
    store: new pgSession({
        pool: pool,
        tableName : 'session' 
    }),
    secret: "species_key",
    cookie: { maxAge: 1 * 60 * 60 * 1000 }, // 1 minuto
    saveUninitialized: false,
    resave: false
}))

// Routes for our api
var worldclimRouter = require('./routes/worldclimrouter')
app.use('/wc', worldclimRouter)


// Start the server
var server = app.listen(port, function () {
  var port = server.address().port
  console.log('Aplicación corriendo en el puerto %s', port)
})

server.setTimeout(60 * 1000 * 15)
module.exports = server




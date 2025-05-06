
/**
 * Express router que monta las funciones asociadas a redes. 
 * @type {object}
 * @const
 * @namespace netRouter
 */
var router = require('express').Router()
var rwcCtrl = require('../controllers/wc_controller')

router.all('/', function(req, res) {
  res.json({ 
    data: { 
      message: '¡Yey! Bienvenido al API de Worldclim'
    }
  })
})


router.route('/variables')
  .get(rwcCtrl.variables)
  .post(rwcCtrl.variables)

router.route('/variables/:id')
  .get(rwcCtrl.get_variable_byid)
  .post(rwcCtrl.get_variable_byid)

router.route('/get-data/:id')
  .get(rwcCtrl.get_data_byid)
  .post(rwcCtrl.get_data_byid)


module.exports = router;
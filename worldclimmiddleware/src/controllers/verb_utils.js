/**
* En este módulo se implementan utilidades comunes para todos los verbos
*
* @exports controllers/verb_utils
* @requires debug
* @requires moment
*/
var verb_utils = {}

const initOptions = {
    error(error, e) {
        if (e.cn) {
            console.log('CN:', e.cn);
            console.log('EVENT:', error.message || error);
        }
    }
};

var debug = require('debug')('verbs:verb_utils')
var moment = require('moment')
var pgp = require('pg-promise')(initOptions)
var config = require('../../config')

/**
 * Pool de conexiones a la base de datos
 */
verb_utils.pool = pgp(config.db);
verb_utils.pool_mallas = pgp(config.db_mallas);


/**
 * Regresa el valor del parametro `name` cuando este presente o
 * `defaultValue`. Verifica los valores en el cuerpo de la petición, {"id":12},
 * y en el query, ej. ?id=12. Se utiliza `BodyParser`.
 *
 * @param {express.Request} req - Express request object
 * @param {string} name - Parameter name
 * @param {Mixed} [defaultValue] - Returned default value if paramters is not
 * defined
 * @return {string}
 *
 */
verb_utils.getParam = function (req, name, defaultValue) {
  var body = req.body || {}
  var query = req.query || {}

  if (body[name] != null) return body[name]
  if (query[name] != null) return query[name]

  return defaultValue
}


verb_utils.makeid = function (length) {
    
    let result = '';
    const characters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
    const charactersLength = characters.length;
    let counter = 0;
    
    while (counter < length) {
      result += characters.charAt(Math.floor(Math.random() * charactersLength));
      counter += 1;
    }
    
    return result;

}


module.exports = verb_utils

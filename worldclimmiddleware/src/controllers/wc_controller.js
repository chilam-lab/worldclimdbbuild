var debug = require('debug')('verbs:auth')
var verb_utils = require('./verb_utils')
var pgp = require('pg-promise')()
var config = require('../../config')

var pool = verb_utils.pool 
var pool_mallas = verb_utils.pool_mallas 


let dic_wc_select = new Map();
dic_wc_select.set('1','select array_agg(bid) as level_id, id_fuentes_bio, (fb.fuente || \' - \' || fb.descripcion) as  descripcion, fb.bins, fb.area')
dic_wc_select.set('2','select array_agg(bid) as level_id, array_agg(layer) as layers, id_fuentes_bio, layer, (fb.fuente || \' - \' || fb.descripcion) as  descripcion, fb.bins, fb.area')
dic_wc_select.set('3','select bid as level_id, tag, id_fuentes_bio, layer, icat, (fb.fuente || \' - \' || fb.descripcion) as  descripcion, fb.bins, fb.area')

let dic_wc_group = new Map();
dic_wc_group.set('1','group by id_fuentes_bio, fb.fuente, fb.descripcion, fb.bins, fb.area')
dic_wc_group.set('2','group by id_fuentes_bio, layer, fb.fuente, fb.descripcion, fb.bins, fb.area')
dic_wc_group.set('3','')

let dic_wc_order = new Map();
dic_wc_order.set('1','order by id_fuentes_bio')
dic_wc_order.set('2','order by id_fuentes_bio, layer')
dic_wc_order.set('3','order by bid')

let valid_filters = ["idfuente","idlayer","idrange"]
let dic_wc_db = new Map();
dic_wc_db.set('idfuente','id_fuentes_bio')
dic_wc_db.set('idlayer','layer')
dic_wc_db.set('idrange','bid')

let fuente_bios = ['bio001','bio002','bio003','bio004','bio005','bio006','bio007','bio008','bio009','bio010','bio011','bio012','bio013','bio014','bio015','bio016','bio017','bio018','bio019']


exports.variables = function(req, res) {

	let { } = req.body;

	// Se recomienda agregar la columna available_grids a este catalogo con ayuda de los servicios disponibles del proyecto regionmiddleware
	pool.any(`with fuentes_wc as(
				select id_fuentes_bio 
				from raster_bins rb 
				group by id_fuentes_bio 
			)
			select 1 as id, 'Fuentes Worldclim' as variable, count(*) level_size, ('{"idfuente":"string"}')::jsonb filter_fields, array[1,2,3,4,5,6]::int[] as available_grids
			from fuentes_wc
			union
			(
			with layers_wc as(
				select layer  
				from raster_bins rb 
				group by layer
				order by layer 
			)
			select 2 as id, 'Layers Worldclim' as variable, count(*) level_size, ('{"idfuente":"string","idlayer":"string"}')::jsonb filter_fields, array[1,2,3,4,5,6]::int[] as available_grids
			from layers_wc
			)
			union
			(
			with ranges_wc as(
				select id_fuentes_bio, layer, icat  
				from raster_bins rb 
				group by id_fuentes_bio,layer, icat 
				order by id_fuentes_bio, layer, icat 
			)
			select 3 as id, 'Ranges Worldclim' as variable, count(*) level_size, ('{"idfuente":"string","idlayer":"string","idrange":"string"}')::jsonb filter_fields, array[1,2,3,4,5,6]::int[] as available_grids
			from ranges_wc
			)
			order by id`, {}).then( 
		function(data) {
			// debug(data);
		res.status(200).json({
			data: data
		})
  	})
  	.catch(error => {
      debug(error)
      res.status(403).json({
      	message: "error al obtener catalogo", 
      	error: error
      })
   	});
}


exports.get_variable_byid = function(req, res) {

	let variable_id = req.params.id
	debug("variable_id: " + variable_id)

	let q = verb_utils.getParam(req, 'q', '')
	let offset = verb_utils.getParam(req, 'offset', 0)
	let limit = verb_utils.getParam(req, 'limit', 10)

	debug("q: " + q)
	debug("offset: " + offset)
	debug("limit: " + limit)

	let query_array = []
	let filter_separator = ";"
	let pair_separator = "="
	let group_separator = ","

	// q: "idfuente = 1; idlayer = bio018; idrange = 300450"
	
	if(q != ""){

		let array_queries = q.split(filter_separator)
		debug(array_queries)

		if(array_queries.length == 0){
			debug("Sin filtros definidos")
		}
		else{
			array_queries.forEach((filter, index) => {

				let filter_pair = filter.split(pair_separator)
				debug(filter_pair)

				if(filter_pair.length == 0){
					debug("Filtro indefinido")
				}
				else{
					
					let filter_param = filter_pair[0].trim()
					debug("filter_param: " + filter_param)


					if(valid_filters.indexOf(filter_param) == -1){
						debug("Filtro invalido")
					}
					else{
						
						if(filter_pair.length != 2){
							debug("Filtro invalido por composición")
						}
						else{
							let filter_value = filter_pair[1].trim().split(group_separator)	
							
							let query_temp = "( "
							filter_value.forEach((value, index) => {

								if(filter_param == "idlayer"){
									value = "'" + value + "'"
								}

								if(index == 0){
									query_temp = query_temp + dic_wc_db.get(filter_param) + " = " + value
								}
								else{
									query_temp = query_temp + " or " + dic_wc_db.get(filter_param) + " = " + value + " "
								}

							})
							query_temp = query_temp + " )"
							query_array.push(query_temp)

						}

					}

				}

			})	

			debug(query_array)

		}

	}


	pool.task(t => {

		val_dic_wc_select = dic_wc_select.get(variable_id)
		val_dic_wc_group = dic_wc_group.get(variable_id)
		val_dic_wc_order = dic_wc_order.get(variable_id)


		let query = `{select}
					from fuentes_bioclimaticas fb 
					join raster_bins rb 
					on fb.id = rb.id_fuentes_bio
					{queries}
					{group}
					{order}`

		query = query.replace("{select}", val_dic_wc_select)
		query = query.replace("{group}", val_dic_wc_group)
		query = query.replace("{order}", val_dic_wc_order)

		query_array.forEach((query_temp, index) => {
			if (index==0) {
				query = query.replace("{queries}", " where " + query_temp + " {queries} ")
			}
			else{
				query = query.replace("{queries}", " and " + query_temp + " {queries} ")
			}
			
		})
		query = query.replace("{queries}", "")

		debug(query)


		return t.any(query).then(resp => {

			let response_array = []

			resp.forEach((item, index) => {

				var temp = {}				

				temp.id = variable_id
				temp.level_id = item.level_id
				temp.data = {}
				if(variable_id == '2' || variable_id == '3')
					temp.data.layer = item.layer					
				if(variable_id == '3')
					temp.data.tag = item.tag					
				temp.data.descripcion = item.descripcion
				temp.data.bins = item.bins
				temp.data.area = item.area
				temp.data.icat = item.icat
				temp.data.idfuente = item.id_fuentes_bio

				response_array.push(temp)

			})

			res.status(200).json({
				data: response_array
			})


		}).catch(error => {
	      debug(error)

	      res.status(403).json({	      	
	      	error: "Error al obtener la malla solicitada", 
	      	message: "error al obtener datos"
	      })
	   	})

	}).catch(error => {
      debug(error)
      res.status(403).json({
      	message: "error general", 
      	error: error
      })
   	});
  	
}



exports.get_data_byid = async function (req, res) {

    try {
        // const id = req.params.id;
        let variable_id = req.params.id
		debug("variable_id: " + variable_id)

        const grid_id = verb_utils.getParam(req, 'grid_id', 1);
        const levels_id = verb_utils.getParam(req, 'levels_id', []);
        const filter_names = verb_utils.getParam(req, 'filter_names', []);
        const filter_values = verb_utils.getParam(req, 'filter_values', []);

        let filter_array = []

        if (levels_id.length === 0) {
            return res.status(404).json({ message: "No se proporcionaron levels_id." });
        }

		if(filter_names.length > 0){
			filter_names.forEach((filter_name, index) => {
				let filter_temp = {}
				filter_temp = {filter_param: filter_name, filter_value: filter_values[index]}
				filter_array.push(filter_temp)
			})
		}


		val_dic_wc_select = dic_wc_select.get(variable_id)
		val_dic_wc_group = dic_wc_group.get(variable_id)
		val_dic_wc_order = dic_wc_order.get(variable_id)


		let queryLevels = `{select}
					from fuentes_bioclimaticas fb 
					join raster_bins rb 
					on fb.id = rb.id_fuentes_bio
					WHERE bid IN ($<bids:raw>)
					{group}
					{order}`

		queryLevels = queryLevels.replace("{select}", val_dic_wc_select)
		queryLevels = queryLevels.replace("{group}", val_dic_wc_group)
		queryLevels = queryLevels.replace("{order}", val_dic_wc_order)


        // const queryLevels = `
        //     SELECT bid, layer, icat, id_fuentes_bio, "label", fb.bins
        //     FROM raster_bins rb
        //     JOIN fuentes_bioclimaticas fb ON fb.id = rb.id_fuentes_bio
        //     WHERE bid IN ($<bids:raw>)
        //     $<filters:raw>
        // `;

        let filter_query = ""

        filter_array.forEach((filter_item) => {	
        	debug(filter_item)

        	if(filter_item.filter_param == "idlayer"){
        		filter_item.filter_value = "'" + filter_item.filter_value + "'"
        	}

			filter_query += filter_query + " and " + dic_wc_db.get(filter_item.filter_param) + " = " + filter_item.filter_value
		})

		// debug("filter_query: " + filter_query)

        // Ejecuta la primera consulta
        const levelsIds = await pool.any(queryLevels, {bids: levels_id.toString(), filters: filter_query});

        debug(levelsIds)
        
        if (levelsIds.length === 0) {
            return res.status(404).json({ message: "No se encontraron niveles." });
        }

        let queryBioParts = [];

		// levelsIds.forEach((item, index) => {
		for(item of levelsIds){

			
            const bid = item.level_id;
            let tableBio;
            let layer;
            let fuentes;
            let icat;
            let data = {}

            data.descripcion = item.descripcion
			data.bins = item.bins
			data.area = item.area
			data.idfuente = item.id_fuentes_bio

			
			if(variable_id == '1'){
				fuentes = item.id_fuentes_bio
				debug("fuentes: " + fuentes)
			}
			if(variable_id == '2' || variable_id == '3'){
				tableBio = `${item.layer}_q${item.bins}`;
				layer = item.layer;
				data.layer = item.layer;
				debug("tableBio: " + tableBio)
				debug("layer: " + layer)
			}
			if(variable_id == '3'){
				icat = item.icat;
				data.tag = item.tag
				data.icat = item.icat	
				debug("icat: " + icat)
            
			}
			
            debug("bid: " + bid)
            debug(data)

            let query_temp = "";
            let poligonResult;

            if(variable_id == '1'){
            	
            	
            	for(idfuente of fuentes.toString()){
            		
            		if(idfuente == 1){
            			q = "_q20"
            		}
            		else if(idfuente == 2){
            			q = "_q10"
            		}
            		debug("q: " + q)
            		
            		let conti = 0

            		query_temp = "with bios as ( "

            		// for(fuente_bio of fuente_bios.slice(0, 2)){
            		for(fuente_bio of fuente_bios){
            			tableBio = fuente_bio + q
            			debug("tableBio: " + tableBio)

            			if(conti == 0){
	            			query_temp = query_temp + `SELECT $<bid:raw> as bid, ST_AsText(ST_SetSRID(ST_Union(the_geom),4326)) as union_geom, '$<data:raw>'::jsonb as datos
		                	FROM ${tableBio} `
	            		}
	            		else{
	            			query_temp = query_temp + ` UNION SELECT $<bid:raw> as bid, ST_AsText(ST_SetSRID(ST_Union(the_geom),4326)) as union_geom, '$<data:raw>'::jsonb as datos
		                	FROM ${tableBio} `
	            		}
	            		conti = conti+1
            		}

            		query_temp = query_temp + ") select bid, datos, ST_AsText(ST_Union(bios.union_geom)) AS union_geom from bios WHERE ST_IsValid(bios.union_geom) GROUP BY bid, datos"

            		debug("query_temp: " + query_temp)

            	}

	            poligonResult = await pool.one(query_temp, {bid: data.idfuente, data: data});

			}
            if(variable_id == '2'){
				query_temp = `SELECT '$<layer:raw>' as bid, ST_AsText(ST_SetSRID(ST_Union(the_geom),4326)) as union_geom, '$<data:raw>'::jsonb as datos
	                FROM $<tableBio:raw>
	                WHERE categoria = '$<layer:raw>'`
	            poligonResult = await pool.one(query_temp, {bid: bid, tableBio: tableBio, layer: layer, data: data});

			}
            if(variable_id == '3'){
            	query_temp = `SELECT $<bid:raw> as bid, ST_AsText(ST_SetSRID(ST_Union(the_geom),4326)) as union_geom, '$<data:raw>'::jsonb as datos
	                FROM $<tableBio:raw>
	                WHERE categoria = '$<layer:raw>' AND icat = $<icat:raw>`
	            poligonResult = await pool.one(query_temp, {bid: bid, tableBio: tableBio, layer: layer, icat:icat, data: data});

            }
            
            queryBioParts.push(poligonResult)

        }

        // debug(queryBioParts)

        debug("grid_id: " + grid_id)

        const query_catgrid_temp = `
                select region_id, table_cell_name 
				from cat_grid cg  
				where grid_id = $<grid_id:raw>`

        const table_cell_item = await pool_mallas.one(query_catgrid_temp, {grid_id: grid_id});

        const tablename = table_cell_item.table_cell_name
        let colunmname = tablename
        colunmname = colunmname.replace(/grid_/g,"")
        colunmname = colunmname.replace(/_aoi/g,"")
        colunmname = "gridid_" + colunmname
        debug("tablename: " + tablename)
        debug("colunmname: " + colunmname)

        let response_array = []

        // queryBioParts.forEach((poligonResult, index) => {
        for(poligonResult of queryBioParts){

        	// debug(poligonResult)
        	
        	query_temp = `with intersectCells as (
							select distinct '$<bid:raw>' as bid, g.$<colunmname:raw> as cell
							from  $<tablename:raw> as g
							join (
								select 
								ST_SetSRID(ST_GeomFromText('$<poligonResult:raw>'),4326) as geom
								) as p
							ON ST_Intersects(g.the_geom, p.geom)
						)
						select bid, array_agg(cell) as cells
						from intersectCells
						group by bid`

			inersectResult = await pool_mallas.one(query_temp, {poligonResult: poligonResult.union_geom, bid: poligonResult.bid, colunmname:colunmname, tablename:tablename});

			response_array.push({
				id: variable_id,
				grid_id: grid_id,
				level_id: inersectResult.bid,
				cells: inersectResult.cells,
				n: inersectResult.cells.length,
				metadata: poligonResult.datos
			})
        	

        }

		res.status(200).json(
			response_array
		)


    } catch (error) {
        debug(error);
        res.status(500).json({ error: "Error al procesar la solicitud.", message: error.message });
    }

};


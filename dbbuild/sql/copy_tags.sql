INSERT INTO raster_bins (tag, icat, layer) VALUES ('{tag}', {icat}, '{layer}')
ON CONFLICT (tag, layer) DO NOTHING
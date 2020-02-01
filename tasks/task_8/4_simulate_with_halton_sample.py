#!/usr/bin/env python3

""" simulate_model.py: obtains a few netronics parameters for a basic tokamak geometry ."""
""" run with python3 simulate_tokamak_model.py | tqdm >> /dev/null """
""" outputs results to a files in json format"""

import json
import os
import numpy as np
from tqdm import tqdm
import uuid
import openmc
from pathlib import Path
from neutronics_material_maker import Material
import ghalton
import pandas as pd

def make_geometry_tallies(batches, nps, enrichment_fraction, inner_radius, thickness, breeder_material_name, temperature_in_C):
    # print('simulating ',batches,enrichment_fraction,inner_radius,thickness,breeder_material_name)

    #MATERIALS from library of materials in neutronics_material_maker package
    breeder_material = Material(material_name = breeder_material_name,
                                enrichment_fraction = enrichment_fraction,
                                temperature_in_C = temperature_in_C).neutronics_material

    eurofer = Material(material_name = 'eurofer').neutronics_material
    copper = Material(material_name = 'copper').neutronics_material

    mats = openmc.Materials([breeder_material, eurofer, copper])
    mats.export_to_xml('materials.xml')


    #GEOMETRY#

    central_sol_surface = openmc.ZCylinder(r=100)
    central_shield_outer_surface = openmc.ZCylinder(r=110)
    first_wall_inner_surface = openmc.Sphere(r=inner_radius)
    first_wall_outer_surface = openmc.Sphere(r=inner_radius+10)
    breeder_blanket_outer_surface = openmc.Sphere(r=inner_radius+10.0+thickness)
    vessel_outer_surface = openmc.Sphere(r=inner_radius+10.0+thickness+10.0, boundary_type='vacuum')

    central_sol_region = -central_sol_surface & -breeder_blanket_outer_surface
    central_sol_cell = openmc.Cell(region=central_sol_region)
    central_sol_cell.fill = copper

    central_shield_region = +central_sol_surface & -central_shield_outer_surface & -breeder_blanket_outer_surface
    central_shield_cell = openmc.Cell(region=central_shield_region)
    central_shield_cell.fill = eurofer

    inner_void_region = -first_wall_inner_surface & +central_shield_outer_surface
    inner_void_cell = openmc.Cell(region=inner_void_region)
    inner_void_cell.name = 'inner_void'

    first_wall_region = -first_wall_outer_surface & +first_wall_inner_surface & +central_shield_outer_surface
    first_wall_cell = openmc.Cell(region=first_wall_region)
    first_wall_cell.fill = eurofer

    breeder_blanket_region = +first_wall_outer_surface & -breeder_blanket_outer_surface & +central_shield_outer_surface
    breeder_blanket_cell = openmc.Cell(region=breeder_blanket_region)
    breeder_blanket_cell.fill = breeder_material

    vessel_region = +breeder_blanket_outer_surface & -vessel_outer_surface
    vessel_cell = openmc.Cell(region=vessel_region)
    vessel_cell.name = 'vessel'
    vessel_cell.fill = eurofer

    universe = openmc.Universe(cells=[central_sol_cell,
                                      central_shield_cell,
                                      inner_void_cell,
                                      first_wall_cell,
                                      breeder_blanket_cell,
                                      vessel_cell])

    #plt.show(universe.plot(width=(1500,1500),basis='xz'))

    geom = openmc.Geometry(universe)


    #SIMULATION SETTINGS#

    sett = openmc.Settings()
    sett.batches = batches
    sett.inactive = 1
    sett.particles = nps
    sett.run_mode = 'fixed source'

    source = openmc.Source()
    source.space = openmc.stats.Point((150, 0, 0))
    source.angle = openmc.stats.Isotropic()
    source.energy = openmc.stats.Discrete([14.08e6], [1])
    sett.source = source

    sett.export_to_xml('settings.xml')


    #tally filters
    particle_filter = openmc.ParticleFilter('neutron')
    cell_filter_breeder = openmc.CellFilter(breeder_blanket_cell)


    #TALLIES#
    tallies = openmc.Tallies()

    tally = openmc.Tally(name='TBR')
    tally.filters = [cell_filter_breeder, particle_filter]
    tally.scores = ['(n,Xt)']
    tallies.append(tally)


    #RUN OPENMC #
    model = openmc.model.Model(geom, mats, sett, tallies)
    model.run()


    #RETRIEVING TALLY RESULTS

    sp = openmc.StatePoint('statepoint.'+str(batches)+'.h5')

    json_output = {}


    tally = sp.get_tally(name='TBR')

    df = tally.get_pandas_dataframe()

    json_output['TBR'] = df['mean'].sum()
    json_output['TBR_std_dev'] = df['std. dev.'].sum()

    return json_output






#reads all json files into pandas dataframe
path_to_json = "outputs"
Path('outputs/').mkdir(parents=True, exist_ok=True)
list_files = [pos_json for pos_json in os.listdir(path_to_json) if pos_json.endswith('.json')]
resultdict = []
for filename in list_files:
    try:
        with open(os.path.join(path_to_json, filename), "r") as inputjson:
            resultdict.append(json.load(inputjson))
    except:
        print('no files created yet')
results_df = pd.DataFrame(resultdict)

number_of_new_simulations = 5 # this value will need to be changed


for i in tqdm(range(number_of_new_simulations)):
    for breeder_material_name in ['Li4SiO4', 'F2Li2BeF2', 'Li', 'Pb84.2Li15.8']:

        sequencer = ghalton.Halton(2)

        if len(results_df) > 0:
            existing_simulations_for_this_material = results_df[results_df['breeder_material_name']==breeder_material_name]

            coords = sequencer.get(number_of_new_simulations+len(existing_simulations_for_this_material))

        else:
            coords = sequencer.get(number_of_new_simulations)

        # x = [item for sublist in x for item in sublist]
        for i, coord in enumerate(coords):

            enrichment_fraction = coord[0]
            thickness = coord[1]*500

            inputs = {'batches':2,
                      'nps':10,  
                      'enrichment_fraction':enrichment_fraction,
                      'inner_radius':500,
                      'thickness':thickness,
                      'breeder_material_name':breeder_material_name,
                      'temperature_in_C':500,
                      }

        result = make_geometry_tallies(**inputs)

        result['sample'] = 'halton'

        result.update(inputs)

        filename = 'outputs/'+str(uuid.uuid4())+'.json'
        with open(filename, mode='w', encoding='utf-8') as f:
            json.dump(result, f, indent=4)
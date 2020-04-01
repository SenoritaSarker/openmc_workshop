#!/usr/bin/env python3

"""4_plot_neutron_birth_location_plasma.py plots neutron birth locations."""

import os

import plotly.graph_objects as go

import openmc

# this copies a pre compiled external neutron source for use in this simulation
os.system('cp /parametric-plasma-source/parametric_plasma_source/source_sampling.so /openmc_workshop/tasks/task_3')


# MATERIALS

mats = openmc.Materials([])

# GEOMETRY

sph1 = openmc.Sphere(r=1000, boundary_type='vacuum')

simple_moderator_cell = openmc.Cell(region=-sph1)

universe = openmc.Universe(cells=[simple_moderator_cell])

geom = openmc.Geometry(universe)


# SIMULATION SETTINGS

# Instantiate a Settings object
sett = openmc.Settings()
batches = 2
sett.batches = batches
sett.inactive = 0
sett.particles = 3000
sett.particle = "neutron"
sett.run_mode = 'fixed source'


# creates a source object
source = openmc.Source()

# sets the source poition, direction and energy with predefined plasma parameters (see source_sampling.cpp)
source.library = './source_sampling.so'

sett.source = source


# Run OpenMC and open statepoint file
model = openmc.model.Model(geom, mats, sett)
sp = openmc.StatePoint(model.run())

print('birth location of first neutron =', sp.source['r'][0])  # these neutrons are all created

fig_coords = go.Figure()

text = ['Energy = '+str(i)+' eV' for i in sp.source['E']]

# plots 3d poisitons of particles coloured by energy

fig_coords.add_trace(go.Scatter3d(x=sp.source['r']['x'],
                                  y=sp.source['r']['y'],
                                  z=sp.source['r']['z'],
                                  hovertext=text,
                                  text=text,
                                  mode='markers',
                                  marker={'size': 1.,
                                          'color': sp.source['E']
                                  }
                    )
                  )

fig_coords.update_layout(title='Neutron production coordinates, coloured by energy')

fig_coords.write_html("plasma_particle_location.html")
try:
    fig_coords.write_html("/my_openmc_workshop/plasma_particle_location.html")
except (FileNotFoundError, NotADirectoryError):  # for both inside and outside docker container
    pass

fig_coords.show()

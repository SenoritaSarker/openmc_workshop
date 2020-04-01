import openmc
from neutronics_material_maker import Material


def simulate_model(
    enrichment,
    thickness,
    breeder_material_name="Li4SiO4",
    temperature_in_C=500,
    batches=2,
    nps=500,
    inner_radius=500,
):

    # MATERIALS from library of materials in neutronics_material_maker package
    breeder_material = Material(material_name=breeder_material_name,
                                enrichment=enrichment,
                                temperature_in_C=temperature_in_C,
                                ).neutronics_material

    SS316 = Material(material_name="SS316").neutronics_material
    copper = Material(material_name="copper").neutronics_material

    mats = openmc.Materials([breeder_material, SS316, copper])
    mats.export_to_xml("materials.xml")

    # GEOMETRY#

    first_wall_inner_surface = openmc.Sphere(r=inner_radius)
    first_wall_outer_surface = openmc.Sphere(r=inner_radius + 10.)
    breeder_blanket_outer_surface = openmc.Sphere(r=inner_radius + 10. + thickness)
    vessel_outer_surface = openmc.Sphere(r=inner_radius + 10.0 + thickness + 10.,
                                         boundary_type="vacuum")

    inner_void_region = -first_wall_inner_surface
    inner_void_cell = openmc.Cell(region=inner_void_region)
    inner_void_cell.name = "inner_void"

    first_wall_region = (-first_wall_outer_surface & 
                        +first_wall_inner_surface)
    first_wall_cell = openmc.Cell(region=first_wall_region)
    first_wall_cell.fill = SS316

    breeder_blanket_region = (+first_wall_outer_surface &
                             -breeder_blanket_outer_surface)
    breeder_blanket_cell = openmc.Cell(region=breeder_blanket_region)
    breeder_blanket_cell.fill = breeder_material

    vessel_region = +breeder_blanket_outer_surface & -vessel_outer_surface
    vessel_cell = openmc.Cell(region=vessel_region)
    vessel_cell.name = "vessel"
    vessel_cell.fill = SS316

    universe = openmc.Universe(cells=[inner_void_cell,
                                      first_wall_cell,
                                      breeder_blanket_cell,
                                      vessel_cell])

    geom = openmc.Geometry(universe)

    # SIMULATION SETTINGS#

    sett = openmc.Settings()
    sett.batches = batches  # this is the minimum number of batches which will be run
    sett.trigger_active = True
    sett.trigger_max_batches = 200   # this is the maximum number of batches which will be run
    sett.inactive = 0
    sett.particles = nps   # as we are using a trigger, we specify a small number of particles per batch
    sett.run_mode = "fixed source"

    source = openmc.Source()
    source.space = openmc.stats.Point((150, 0, 0))
    source.angle = openmc.stats.Isotropic()
    source.energy = openmc.stats.Discrete([14.08e6], [1])
    sett.source = source

    # sett.export_to_xml("settings.xml")

    # tally filters
    particle_filter = openmc.ParticleFilter("neutron")
    cell_filter_breeder = openmc.CellFilter(breeder_blanket_cell)

    # TALLIES#
    tallies = openmc.Tallies()

    tally = openmc.Tally(name="TBR")
    tally.filters = [cell_filter_breeder, particle_filter]
    tally.scores = ["(n,Xt)"]
    tally.triggers = [openmc.Trigger(trigger_type='std_dev', threshold=0.01)]
    tallies.append(tally)

    # Run OpenMC and open statepoint file
    model = openmc.model.Model(geom, mats, sett, tallies)
    sp = openmc.StatePoint(model.run(output=False))

    json_output = {
        "batches": batches,
        "nps": nps,
        "enrichment": enrichment,
        "inner_radius": inner_radius,
        "thickness": thickness,
        "breeder_material_name": breeder_material_name,
        "temperature_in_C": temperature_in_C,
    }

    # Extract tally results

    tally = sp.get_tally(name="TBR")

    df = tally.get_pandas_dataframe()

    json_output["TBR"] = df["mean"].sum()
    json_output["TBR_std_dev"] = df["std. dev."].sum()

    return json_output

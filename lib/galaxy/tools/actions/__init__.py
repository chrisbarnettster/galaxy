import json
import re

from galaxy.exceptions import ObjectInvalid
from galaxy.model import LibraryDatasetDatasetAssociation
from galaxy import model
from galaxy.tools.parameters.basic import DataCollectionToolParameter, DataToolParameter
from galaxy.tools.parameters.wrapped import WrappedParameters
from galaxy.util import ExecutionTimer
from galaxy.util.json import dumps
from galaxy.util.none_like import NoneDataset
from galaxy.util.odict import odict
from galaxy.util.template import fill_template
from galaxy.web import url_for

import logging
log = logging.getLogger( __name__ )


class ToolAction( object ):
    """
    The actions to be taken when a tool is run (after parameters have
    been converted and validated).
    """
    def execute( self, tool, trans, incoming={}, set_output_hid=True ):
        raise TypeError("Abstract method")


class DefaultToolAction( object ):
    """Default tool action is to run an external command"""

    def collect_input_datasets( self, tool, param_values, trans ):
        """
        Collect any dataset inputs from incoming. Returns a mapping from
        parameter name to Dataset instance for each tool parameter that is
        of the DataToolParameter type.
        """
        input_datasets = odict()

        def visitor( prefix, input, value, parent=None ):

            def process_dataset( data, formats=None ):
                if not data:
                    return data
                if formats is None:
                    formats = input.formats
                if not data.datatype.matches_any( formats ):
                    # Need to refresh in case this conversion just took place, i.e. input above in tool performed the same conversion
                    trans.sa_session.refresh( data )
                    target_ext, converted_dataset = data.find_conversion_destination( formats )
                    if target_ext:
                        if converted_dataset:
                            data = converted_dataset
                        else:
                            # FIXME: merge with hda.get_converted_dataset() mode as it's nearly identical.
                            # run converter here
                            new_data = data.datatype.convert_dataset( trans, data, target_ext, return_output=True, visible=False ).values()[0]
                            new_data.hid = data.hid
                            new_data.name = data.name
                            trans.sa_session.add( new_data )
                            assoc = trans.app.model.ImplicitlyConvertedDatasetAssociation( parent=data, file_type=target_ext, dataset=new_data, metadata_safe=False )
                            trans.sa_session.add( assoc )
                            trans.sa_session.flush()
                            data = new_data
                current_user_roles = trans.get_current_user_roles()
                if not trans.app.security_agent.can_access_dataset( current_user_roles, data.dataset ):
                    raise "User does not have permission to use a dataset (%s) provided for input." % data.id
                return data
            if isinstance( input, DataToolParameter ):
                if isinstance( value, list ):
                    # If there are multiple inputs with the same name, they
                    # are stored as name1, name2, ...
                    for i, v in enumerate( value ):
                        processed_dataset = process_dataset( v )
                        if i == 0:
                            # Allow copying metadata to output, first item will be source.
                            input_datasets[ prefix + input.name ] = processed_dataset
                        input_datasets[ prefix + input.name + str( i + 1 ) ] = processed_dataset
                        conversions = []
                        for conversion_name, conversion_extensions, conversion_datatypes in input.conversions:
                            new_data = process_dataset( input_datasets[ prefix + input.name + str( i + 1 ) ], conversion_datatypes )
                            if not new_data or new_data.datatype.matches_any( conversion_datatypes ):
                                input_datasets[ prefix + conversion_name + str( i + 1 ) ] = new_data
                                conversions.append( ( conversion_name, new_data ) )
                            else:
                                raise Exception('A path for explicit datatype conversion has not been found: %s --/--> %s' % ( input_datasets[ prefix + input.name + str( i + 1 ) ].extension, conversion_extensions ) )
                        if parent:
                            parent[input.name][i] = input_datasets[ prefix + input.name + str( i + 1 ) ]
                            for conversion_name, conversion_data in conversions:
                                # allow explicit conversion to be stored in job_parameter table
                                parent[ conversion_name ][i] = conversion_data.id  # a more robust way to determine JSONable value is desired
                        else:
                            param_values[input.name][i] = input_datasets[ prefix + input.name + str( i + 1 ) ]
                            for conversion_name, conversion_data in conversions:
                                # allow explicit conversion to be stored in job_parameter table
                                param_values[ conversion_name ][i] = conversion_data.id  # a more robust way to determine JSONable value is desired
                else:
                    input_datasets[ prefix + input.name ] = process_dataset( value )
                    conversions = []
                    for conversion_name, conversion_extensions, conversion_datatypes in input.conversions:
                        new_data = process_dataset( input_datasets[ prefix + input.name ], conversion_datatypes )
                        if not new_data or new_data.datatype.matches_any( conversion_datatypes ):
                            input_datasets[ prefix + conversion_name ] = new_data
                            conversions.append( ( conversion_name, new_data ) )
                        else:
                            raise Exception( 'A path for explicit datatype conversion has not been found: %s --/--> %s' % ( input_datasets[ prefix + input.name ].extension, conversion_extensions ) )
                    target_dict = parent
                    if not target_dict:
                        target_dict = param_values
                    target_dict[ input.name ] = input_datasets[ prefix + input.name ]
                    for conversion_name, conversion_data in conversions:
                        # allow explicit conversion to be stored in job_parameter table
                        target_dict[ conversion_name ] = conversion_data.id  # a more robust way to determine JSONable value is desired
            elif isinstance( input, DataCollectionToolParameter ):
                if not value:
                    return
                for i, v in enumerate( value.collection.dataset_instances ):
                    data = v
                    current_user_roles = trans.get_current_user_roles()
                    if not trans.app.security_agent.can_access_dataset( current_user_roles, data.dataset ):
                        raise Exception( "User does not have permission to use a dataset (%s) provided for input." % data.id )
                    # Skipping implicit conversion stuff for now, revisit at
                    # some point and figure out if implicitly converting a
                    # dataset collection makes senese.

                    # if i == 0:
                    #    # Allow copying metadata to output, first item will be source.
                    #    input_datasets[ prefix + input.name ] = data.dataset_instance
                    input_datasets[ prefix + input.name + str( i + 1 ) ] = data

        tool.visit_inputs( param_values, visitor )
        return input_datasets

    def collect_input_dataset_collections( self, tool, param_values ):
        input_dataset_collections = dict()

        def visitor( prefix, input, value, parent=None ):
            if isinstance( input, DataToolParameter ):
                if isinstance( value, model.HistoryDatasetCollectionAssociation ):
                    input_dataset_collections[ prefix + input.name ] = ( value, True )
                    target_dict = parent
                    if not target_dict:
                        target_dict = param_values
                    # This is just a DataToolParameter, so replace this
                    # collection with individual datasets. Database will still
                    # record collection which should be enought for workflow
                    # extraction and tool rerun.
                    target_dict[ input.name ] = value.collection.dataset_instances[:]  # shallow copy
            elif isinstance( input, DataCollectionToolParameter ):
                input_dataset_collections[ prefix + input.name ] = ( value, False )

        tool.visit_inputs( param_values, visitor )
        return input_dataset_collections

    def execute(self, tool, trans, incoming={}, return_job=False, set_output_hid=True, set_output_history=True, history=None, job_params=None, rerun_remap_job_id=None, mapping_over_collection=False):
        """
        Executes a tool, creating job and tool outputs, associating them, and
        submitting the job to the job queue. If history is not specified, use
        trans.history as destination for tool's output datasets.
        """
        assert tool.allow_user_access( trans.user ), "User (%s) is not allowed to access this tool." % ( trans.user )
        # Set history.
        if not history:
            history = tool.get_default_history_by_trans( trans, create=True )

        out_data = odict()
        out_collections = {}
        out_collection_instances = {}
        # Track input dataset collections - but replace with simply lists so collect
        # input datasets can process these normally.
        inp_dataset_collections = self.collect_input_dataset_collections( tool, incoming )
        # Collect any input datasets from the incoming parameters
        inp_data = self.collect_input_datasets( tool, incoming, trans )

        # Deal with input dataset names, 'dbkey' and types
        input_names = []
        input_ext = 'data'
        input_dbkey = incoming.get( "dbkey", "?" )
        inp_items = inp_data.items()
        inp_items.reverse()
        for name, data in inp_items:
            if not data:
                data = NoneDataset( datatypes_registry=trans.app.datatypes_registry )
                continue

            # Convert LDDA to an HDA.
            if isinstance(data, LibraryDatasetDatasetAssociation):
                data = data.to_history_dataset_association( None )
                inp_data[name] = data

            else:  # HDA
                if data.hid:
                    input_names.append( 'data %s' % data.hid )
            input_ext = data.ext

            if data.dbkey not in [None, '?']:
                input_dbkey = data.dbkey

            identifier = getattr( data, "element_identifier", None )
            if identifier is not None:
                incoming[ "%s|__identifier__" % name ] = identifier

        # Collect chromInfo dataset and add as parameters to incoming
        ( chrom_info, db_dataset ) = trans.app.genome_builds.get_chrom_info( input_dbkey, trans=trans, custom_build_hack_get_len_from_fasta_conversion=tool.id != 'CONVERTER_fasta_to_len' )
        if db_dataset:
            inp_data.update( { "chromInfo": db_dataset } )
        incoming[ "chromInfo" ] = chrom_info

        # Determine output dataset permission/roles list
        existing_datasets = [ inp for inp in inp_data.values() if inp ]
        if existing_datasets:
            output_permissions = trans.app.security_agent.guess_derived_permissions_for_datasets( existing_datasets )
        else:
            # No valid inputs, we will use history defaults
            output_permissions = trans.app.security_agent.history_get_default_permissions( history )

        # Build name for output datasets based on tool name and input names
        on_text = on_text_for_names( input_names )

        # Add the dbkey to the incoming parameters
        incoming[ "dbkey" ] = input_dbkey
        # wrapped params are used by change_format action and by output.label; only perform this wrapping once, as needed
        wrapped_params = WrappedParameters( trans, tool, incoming )
        # Keep track of parent / child relationships, we'll create all the
        # datasets first, then create the associations
        parent_to_child_pairs = []
        child_dataset_names = set()
        object_store_populator = ObjectStorePopulator( trans.app )

        def handle_output( name, output ):
            if output.parent:
                parent_to_child_pairs.append( ( output.parent, name ) )
                child_dataset_names.add( name )
            # What is the following hack for? Need to document under what
            # conditions can the following occur? (james@bx.psu.edu)
            # HACK: the output data has already been created
            #      this happens i.e. as a result of the async controller
            if name in incoming:
                dataid = incoming[name]
                data = trans.sa_session.query( trans.app.model.HistoryDatasetAssociation ).get( dataid )
                assert data is not None
                out_data[name] = data
            else:
                ext = determine_output_format(
                    output,
                    wrapped_params.params,
                    inp_data,
                    inp_dataset_collections,
                    input_ext
                )
                data = trans.app.model.HistoryDatasetAssociation( extension=ext, create_dataset=True, flush=False )
                if output.hidden:
                    data.visible = False
                trans.sa_session.add( data )
                trans.app.security_agent.set_all_dataset_permissions( data.dataset, output_permissions, new=True )
                trans.sa_session.flush()

            object_store_populator.set_object_store_id( data )

            # This may not be neccesary with the new parent/child associations
            data.designation = name
            # Copy metadata from one of the inputs if requested.

            # metadata source can be either a string referencing an input
            # or an actual object to copy.
            metadata_source = output.metadata_source
            if metadata_source:
                if isinstance( metadata_source, basestring ):
                    metadata_source = inp_data[metadata_source]

            if metadata_source is not None:
                data.init_meta( copy_from=metadata_source )
            else:
                data.init_meta()
            # Take dbkey from LAST input
            data.dbkey = str(input_dbkey)
            # Set state
            # FIXME: shouldn't this be NEW until the job runner changes it?
            data.state = data.states.QUEUED
            data.blurb = "queued"
            # Set output label
            data.name = self.get_output_name( output, data, tool, on_text, trans, incoming, history, wrapped_params.params, job_params )
            # Store output
            out_data[ name ] = data
            if output.actions:
                # Apply pre-job tool-output-dataset actions; e.g. setting metadata, changing format
                output_action_params = dict( out_data )
                output_action_params.update( incoming )
                output.actions.apply_action( data, output_action_params )
            # Store all changes to database
            # Updates at least state, blurb, and name. Does a query before
            # hand I don't know why...
            trans.sa_session.flush()
            return data

        for name, output in tool.outputs.items():
            if not filter_output(output, incoming):
                if output.collection:
                    collections_manager = trans.app.dataset_collections_service
                    # As far as I can tell - this is always true - but just verify
                    assert set_output_history, "Cannot create dataset collection for this kind of tool."

                    element_identifiers = []
                    input_collections = dict( [ (k, v[0]) for k, v in inp_dataset_collections.iteritems() ] )
                    known_outputs = output.known_outputs( input_collections, collections_manager.type_registry )
                    # Just to echo TODO elsewhere - this should be restructured to allow
                    # nested collections.
                    for output_part_def in known_outputs:
                        # Add elements to top-level collection, unless nested...
                        current_element_identifiers = element_identifiers
                        current_collection_type = output.structure.collection_type

                        for parent_id in (output_part_def.parent_ids or []):
                            # TODO: replace following line with formal abstractions for doing this.
                            current_collection_type = ":".join(current_collection_type.split(":")[1:])
                            name_to_index = dict(map(lambda (index, value): (value["name"], index), enumerate(current_element_identifiers)))
                            if parent_id not in name_to_index:
                                if parent_id not in current_element_identifiers:
                                    index = len(current_element_identifiers)
                                    current_element_identifiers.append(dict(
                                        name=parent_id,
                                        collection_type=current_collection_type,
                                        src="new_collection",
                                        element_identifiers=[],
                                    ))
                                else:
                                    index = name_to_index[parent_id]
                            current_element_identifiers = current_element_identifiers[ index ][ "element_identifiers" ]

                        effective_output_name = output_part_def.effective_output_name
                        element = handle_output( effective_output_name, output_part_def.output_def )
                        # Following hack causes dataset to no be added to history...
                        child_dataset_names.add( effective_output_name )

                        if set_output_history:
                            history.add_dataset( element, set_hid=set_output_hid )
                        trans.sa_session.add( element )
                        trans.sa_session.flush()

                        current_element_identifiers.append({
                            "__object__": element,
                            "name": output_part_def.element_identifier,
                        })
                        log.info(element_identifiers)

                    if output.dynamic_structure:
                        assert not element_identifiers  # known_outputs must have been empty
                        element_kwds = dict(elements=collections_manager.ELEMENTS_UNINITIALIZED)
                    else:
                        element_kwds = dict(element_identifiers=element_identifiers)

                    collection_type = output.structure.collection_type
                    if collection_type is None:
                        collection_type_source = output.structure.collection_type_source
                        if collection_type_source is None:
                            # TODO: Not a new problem, but this should be determined
                            # sooner.
                            raise Exception("Could not determine collection type to create.")
                        if collection_type_source not in input_collections:
                            raise Exception("Could not find collection type source with name [%s]." % collection_type_source)

                        collection_type = input_collections[collection_type_source].collection.collection_type

                    if mapping_over_collection:
                        dc = collections_manager.create_dataset_collection(
                            trans,
                            collection_type=collection_type,
                            **element_kwds
                        )
                        out_collections[ name ] = dc
                    else:
                        hdca_name = self.get_output_name( output, None, tool, on_text, trans, incoming, history, wrapped_params.params, job_params )
                        hdca = collections_manager.create(
                            trans,
                            history,
                            name=hdca_name,
                            collection_type=collection_type,
                            trusted_identifiers=True,
                            **element_kwds
                        )
                        # name here is name of the output element - not name
                        # of the hdca.
                        out_collection_instances[ name ] = hdca
                else:
                    handle_output_timer = ExecutionTimer()
                    handle_output( name, output )
                    log.info("Handled output %s" % handle_output_timer)
        # Add all the top-level (non-child) datasets to the history unless otherwise specified
        for name in out_data.keys():
            if name not in child_dataset_names and name not in incoming:  # don't add children; or already existing datasets, i.e. async created
                data = out_data[ name ]
                if set_output_history:
                    # Set HID and add to history.
                    # This is brand new and certainly empty so don't worry about quota.
                    history.add_dataset( data, set_hid=set_output_hid, quota=False )
                trans.sa_session.add( data )
                trans.sa_session.flush()
        # Add all the children to their parents
        for parent_name, child_name in parent_to_child_pairs:
            parent_dataset = out_data[ parent_name ]
            child_dataset = out_data[ child_name ]
            parent_dataset.children.append( child_dataset )
        # Store data after custom code runs
        trans.sa_session.flush()
        # Create the job object
        job = trans.app.model.Job()

        if hasattr( trans, "get_galaxy_session" ):
            galaxy_session = trans.get_galaxy_session()
            # If we're submitting from the API, there won't be a session.
            if type( galaxy_session ) == trans.model.GalaxySession:
                job.session_id = galaxy_session.id
        if trans.user is not None:
            job.user_id = trans.user.id
        job.history_id = history.id
        job.tool_id = tool.id
        try:
            # For backward compatibility, some tools may not have versions yet.
            job.tool_version = tool.version
        except:
            job.tool_version = "1.0.0"
        # FIXME: Don't need all of incoming here, just the defined parameters
        #        from the tool. We need to deal with tools that pass all post
        #        parameters to the command as a special case.
        for name, ( dataset_collection, reduced ) in inp_dataset_collections.iteritems():
            # TODO: Does this work if nested in repeat/conditional?
            if reduced:
                incoming[ name ] = "__collection_reduce__|%s" % dataset_collection.id
            # Should verify security? We check security of individual
            # datasets below?
            job.add_input_dataset_collection( name, dataset_collection )
        for name, value in tool.params_to_strings( incoming, trans.app ).iteritems():
            job.add_parameter( name, value )
        current_user_roles = trans.get_current_user_roles()
        access_timer = ExecutionTimer()
        for name, dataset in inp_data.iteritems():
            if dataset:
                if not trans.app.security_agent.can_access_dataset( current_user_roles, dataset.dataset ):
                    raise Exception("User does not have permission to use a dataset (%s) provided for input." % data.id)
                job.add_input_dataset( name, dataset )
            else:
                job.add_input_dataset( name, None )
        log.info("Verified access to datasets %s" % access_timer)
        for name, dataset in out_data.iteritems():
            job.add_output_dataset( name, dataset )
        for name, dataset_collection in out_collections.iteritems():
            job.add_implicit_output_dataset_collection( name, dataset_collection )
        for name, dataset_collection_instance in out_collection_instances.iteritems():
            job.add_output_dataset_collection( name, dataset_collection_instance )
        job.object_store_id = object_store_populator.object_store_id
        if job_params:
            job.params = dumps( job_params )
        job.set_handler(tool.get_job_handler(job_params))
        trans.sa_session.add( job )
        # Now that we have a job id, we can remap any outputs if this is a rerun and the user chose to continue dependent jobs
        # This functionality requires tracking jobs in the database.
        if trans.app.config.track_jobs_in_database and rerun_remap_job_id is not None:
            try:
                old_job = trans.sa_session.query( trans.app.model.Job ).get(rerun_remap_job_id)
                assert old_job is not None, '(%s/%s): Old job id is invalid' % (rerun_remap_job_id, job.id)
                assert old_job.tool_id == job.tool_id, '(%s/%s): Old tool id (%s) does not match rerun tool id (%s)' % (old_job.id, job.id, old_job.tool_id, job.tool_id)
                if trans.user is not None:
                    assert old_job.user_id == trans.user.id, '(%s/%s): Old user id (%s) does not match rerun user id (%s)' % (old_job.id, job.id, old_job.user_id, trans.user.id)
                elif trans.user is None and type( galaxy_session ) == trans.model.GalaxySession:
                    assert old_job.session_id == galaxy_session.id, '(%s/%s): Old session id (%s) does not match rerun session id (%s)' % (old_job.id, job.id, old_job.session_id, galaxy_session.id)
                else:
                    raise Exception('(%s/%s): Remapping via the API is not (yet) supported' % (old_job.id, job.id))
                # Duplicate PJAs before remap.
                for pjaa in old_job.post_job_actions:
                    job.add_post_job_action(pjaa.post_job_action)
                for jtod in old_job.output_datasets:
                    for (job_to_remap, jtid) in [(jtid.job, jtid) for jtid in jtod.dataset.dependent_jobs]:
                        if (trans.user is not None and job_to_remap.user_id == trans.user.id) or (trans.user is None and job_to_remap.session_id == galaxy_session.id):
                            if job_to_remap.state == job_to_remap.states.PAUSED:
                                job_to_remap.state = job_to_remap.states.NEW
                            for hda in [ dep_jtod.dataset for dep_jtod in job_to_remap.output_datasets ]:
                                if hda.state == hda.states.PAUSED:
                                    hda.state = hda.states.NEW
                                    hda.info = None
                            for p in job_to_remap.parameters:
                                if p.name == jtid.name and p.value == str(jtod.dataset.id):
                                    p.value = str(out_data[jtod.name].id)
                            jtid.dataset = out_data[jtod.name]
                            jtid.dataset.hid = jtod.dataset.hid
                            log.info('Job %s input HDA %s remapped to new HDA %s' % (job_to_remap.id, jtod.dataset.id, jtid.dataset.id))
                            trans.sa_session.add(job_to_remap)
                            trans.sa_session.add(jtid)
                    jtod.dataset.visible = False
                    trans.sa_session.add(jtod)
            except Exception:
                log.exception('Cannot remap rerun dependencies.')
        trans.sa_session.flush()
        # Some tools are not really executable, but jobs are still created for them ( for record keeping ).
        # Examples include tools that redirect to other applications ( epigraph ).  These special tools must
        # include something that can be retrieved from the params ( e.g., REDIRECT_URL ) to keep the job
        # from being queued.
        if 'REDIRECT_URL' in incoming:
            # Get the dataset - there should only be 1
            for name in inp_data.keys():
                dataset = inp_data[ name ]
            redirect_url = tool.parse_redirect_url( dataset, incoming )
            # GALAXY_URL should be include in the tool params to enable the external application
            # to send back to the current Galaxy instance
            GALAXY_URL = incoming.get( 'GALAXY_URL', None )
            assert GALAXY_URL is not None, "GALAXY_URL parameter missing in tool config."
            redirect_url += "&GALAXY_URL=%s" % GALAXY_URL
            # Job should not be queued, so set state to ok
            job.set_state( trans.app.model.Job.states.OK )
            job.info = "Redirected to: %s" % redirect_url
            trans.sa_session.add( job )
            trans.sa_session.flush()
            trans.response.send_redirect( url_for( controller='tool_runner', action='redirect', redirect_url=redirect_url ) )
        else:
            # Put the job in the queue if tracking in memory
            trans.app.job_queue.put( job.id, job.tool_id )
            trans.log_event( "Added job to the job queue, id: %s" % str(job.id), tool_id=job.tool_id )
            return job, out_data

    def get_output_name( self, output, dataset, tool, on_text, trans, incoming, history, params, job_params ):
        if output.label:
            params['tool'] = tool
            params['on_string'] = on_text
            return fill_template( output.label, context=params )
        else:
            return self._get_default_data_name( dataset, tool, on_text=on_text, trans=trans, incoming=incoming, history=history, params=params, job_params=job_params )

    def _get_default_data_name( self, dataset, tool, on_text=None, trans=None, incoming=None, history=None, params=None, job_params=None, **kwd ):
        name = tool.name
        if on_text:
            name += ( " on " + on_text )
        return name


class ObjectStorePopulator( object ):
    """ Small helper for interacting with the object store and making sure all
    datasets from a job end up with the same object_store_id.
    """

    def __init__( self, app ):
        self.object_store = app.object_store
        self.object_store_id = None

    def set_object_store_id( self, data ):
        # Create an empty file immediately.  The first dataset will be
        # created in the "default" store, all others will be created in
        # the same store as the first.
        data.dataset.object_store_id = self.object_store_id
        try:
            self.object_store.create( data.dataset )
        except ObjectInvalid:
            raise Exception('Unable to create output dataset: object store is full')
        self.object_store_id = data.dataset.object_store_id  # these will be the same thing after the first output


def on_text_for_names( input_names ):
    # input_names may contain duplicates... this is because the first value in
    # multiple input dataset parameters will appear twice once as param_name
    # and once as param_name1.
    unique_names = []
    for name in input_names:
        if name not in unique_names:
            unique_names.append( name )
    input_names = unique_names

    # Build name for output datasets based on tool name and input names
    if len( input_names ) == 1:
        on_text = input_names[0]
    elif len( input_names ) == 2:
        on_text = '%s and %s' % tuple(input_names[0:2])
    elif len( input_names ) == 3:
        on_text = '%s, %s, and %s' % tuple(input_names[0:3])
    elif len( input_names ) > 3:
        on_text = '%s, %s, and others' % tuple(input_names[0:2])
    else:
        on_text = ""
    return on_text


def filter_output(output, incoming):
    for filter in output.filters:
        try:
            if not eval( filter.text.strip(), globals(), incoming ):
                return True  # do not create this dataset
        except Exception, e:
            log.debug( 'Dataset output filter failed: %s' % e )
    return False


def determine_output_format(output, parameter_context, input_datasets, input_dataset_collections, random_input_ext):
    """ Determines the output format for a dataset based on an abstract
    description of the output (galaxy.tools.ToolOutput), the parameter
    wrappers, a map of the input datasets (name => HDA), and the last input
    extensions in the tool form.

    TODO: Don't deal with XML here - move this logic into ToolOutput.
    TODO: Make the input extension used deterministic instead of random.
    """
    # the type should match the input
    ext = output.format
    if ext == "input":
        ext = random_input_ext
    format_source = output.format_source
    if format_source is not None and format_source in input_datasets:
        try:
            input_dataset = input_datasets[output.format_source]
            input_extension = input_dataset.ext
            ext = input_extension
        except Exception:
            pass
    elif format_source is not None:
        if re.match(r"^[^\[\]]*\[[^\[\]]*\]$", format_source):
            collection_name, element_index = format_source[0:-1].split("[")
            # Treat as json to interpret "forward" vs 0 with type
            # Make it feel more like Python, single quote better in XML also.
            element_index = element_index.replace("'", '"')
            element_index = json.loads(element_index)

            if collection_name in input_dataset_collections:
                try:
                    input_collection = input_dataset_collections[collection_name][0]
                    input_dataset = input_collection.collection[element_index].element_object
                    input_extension = input_dataset.ext
                    ext = input_extension
                except Exception, e:
                    log.debug("Exception while trying to determine format_source: %s", e)
                    pass

    # process change_format tags
    if output.change_format is not None:
        new_format_set = False
        for change_elem in output.change_format:
            for when_elem in change_elem.findall( 'when' ):
                check = when_elem.get( 'input', None )
                if check is not None:
                    try:
                        if '$' not in check:
                            # allow a simple name or more complex specifications
                            check = '${%s}' % check
                        if str( fill_template( check, context=parameter_context ) ) == when_elem.get( 'value', None ):
                            ext = when_elem.get( 'format', ext )
                    except:  # bad tag input value; possibly referencing a param within a different conditional when block or other nonexistent grouping construct
                        continue
                else:
                    check = when_elem.get( 'input_dataset', None )
                    if check is not None:
                        check = input_datasets.get( check, None )
                        # At this point check is a HistoryDatasetAssociation object.
                        check_format = when_elem.get( 'format', ext )
                        check_value = when_elem.get( 'value', None )
                        check_attribute = when_elem.get( 'attribute', None )
                        if check is not None and check_value is not None and check_attribute is not None:
                            # See if the attribute to be checked belongs to the HistoryDatasetAssociation object.
                            if hasattr( check, check_attribute ):
                                if str( getattr( check, check_attribute ) ) == str( check_value ):
                                    ext = check_format
                                    new_format_set = True
                                    break
                            # See if the attribute to be checked belongs to the metadata associated with the
                            # HistoryDatasetAssociation object.
                            if check.metadata is not None:
                                metadata_value = check.metadata.get( check_attribute, None )
                                if metadata_value is not None:
                                    if str( metadata_value ) == str( check_value ):
                                        ext = check_format
                                        new_format_set = True
                                        break
            if new_format_set:
                break
    return ext

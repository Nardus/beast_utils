# Add GLM predictors to a BEAST xml file

import numpy as np

from warnings import warn
from lxml import objectify


# Internal functions
def _parse_glm_specification(xml_root, model_id, datatype_id):
    """
    Parse relevant components of a BEAST XML specifying a GLM, checking validity and capturing 
    the order of states. Returns the <glmSubstitutionModel> element specifying the GLM, along 
    with all states defined in the XML's <dataType> block.
    
    Parameters
    ----------
    xml_root : xml.etree.ElementTree.Element
        The root element of the XML file.
    model_id : str
        The id of the <glmSubstitutionModel> block to retrieve.
    datatype_id : str
        The id of the <dataType> block defining trait values (states) for this model.
        
    Returns
    -------
    tuple
        A tuple containing the <glmSubstitutionModel> block and a list of states.
    """
    # Find the <glmSubstitutionModel> block (there may be more than one)
    model_spec = xml_root.find(f"glmSubstitutionModel[@id='{model_id}']")
    
    if model_spec is None:
        raise ValueError(f"No <glmSubstitutionModel> block with id '{model_id}' found.")
        
    # Find the correct <generalDataType> block
    datatype_spec = xml_root.find(f"generalDataType[@id='{datatype_id}']")
    
    if datatype_spec is None:
        raise ValueError(f"No <generalDataType> block with id '{datatype_id}' found.")
    
    # Retrieve order of observed states
    states = [state.get("code") for state in datatype_spec.iterchildren("state")]
    
    return model_spec, states


def _apply_tranformations(data, log, standardise):
    """
    Transform predictor data. If both `log` and `standardise` are True, the data will be 
    log-transformed and then standardised. This matches the order of these operations in 
    the [BEAUTI source code](https://github.com/beast-dev/beast-mcmc/blob/cf3d7370ca1a5b697f0f49be49765dcd6ad06dfb/src/dr/app/beauti/options/Predictor.java#L218).
    
    Standardisation is done by subtracting the mean and dividing by the standard deviation. Note
    that calculation of the mean and standard deviation *ignores* the diagonal, matching the
    transformation applied by BEAUTI.
    
    Neither transformation will be applied to the diagonal, which will be set to `NaN` instead.
    
    Parameters
    ----------
    data : numpy.array
        Predictor data.
    scale : bool
        Whether to scale the data.
    log : bool
        Whether to log-transform the data.
    """
    if not isinstance(data, np.ndarray):
        raise ValueError("Data should be a numpy array.")
        
    if data.shape[0] != data.shape[1]:
        raise ValueError("Expected a square matrix.")
    
    data = data.astype(float)
    not_diagonal = ~np.eye(data.shape[0], dtype=bool)
        
    if log:
        # Don't log diagonal, which might contain 0's (these are dropped later anyway)
        if (data[not_diagonal] <= 0).any():
            raise ValueError("Cannot log-transform predictor values <= 0.")
        
        data = np.log(data, out=data, where=not_diagonal)
    
    if standardise:
        mean = np.mean(data, where=not_diagonal)
        sd = np.std(data, where=not_diagonal)
        
        data[not_diagonal] = (data[not_diagonal] - mean) / sd
        
    # Transformations not applied to diagonal elements, so set to NaN to avoid confusion
    data[~not_diagonal] = np.nan
    
    return data


def _flatten_matrix(mat):
    """
    Convert a matrix to the flat representation used in BEAST XML files. The order of values will 
    match the conversion done by BEAUTI (see [Predictor.getValueString()](https://github.com/beast-dev/beast-mcmc/blob/cf3d7370ca/src/dr/app/beauti/options/Predictor.java#L256)), 
    which flattens the upper and lower triangles of each matrix separately, with results 
    concatenated (dropping the diagonal). It flattens the upper triangle row-wise, but the 
    lower triangle column-wise.
    
    Parameters
    ----------
    mat : numpy.ndarray
        A matrix.
    
    Returns
    -------
    str
        The matrix as a flat string.
    """
    if mat.shape[0] != mat.shape[1]:
        raise ValueError("Expected a square matrix.")
    
    # Flatten upper triangle row-by-row
    upper_inds = np.triu_indices_from(mat, 1)
    values = mat[upper_inds].tolist()
    
    # Lower triangle column-by-column is equivalent to transposing (rows become columns),
    # then getting the upper triangle row-by-row
    values += mat.T[upper_inds].tolist()
    
    # Convert to string
    values = [str(v) for v in values]
    
    return " ".join(values)


def _build_scalar_predictor(data, observed_states, direction):
    """
    Build a predictor string from a scalar feature.
    
    Parameters
    ----------
    data : pandas.DataFrame
        A DataFrame containing the predictor values. The index should refer to observed states
        (e.g. locations), and the first column should be the predictor values. Any additional
        columns will be ignored.
    observed_states : list of str
        A list of observed states (e.g. locations) in the order they appear in the XML.
    direction : int
        Direction of the trait matrix to build (0 for origin, 1 for destination).
        
    Returns
    -------
    numpy.ndarray
        A matrix of predictor values.
    """
    # Check inputs
    if direction not in [0, 1]:
        raise ValueError("direction must be 0 or 1.")
    
    if data.shape[1] != 1:
        warn("Data has more than one column. Only the first column will be used.",
             stacklevel=3, category=RuntimeWarning)    
        data = data.iloc[:, 0]
    
    # Define order of states
    state_matrix = [[l] * len(observed_states) for l in observed_states]
    state_matrix = np.array(state_matrix)
    
    if direction == 1:
        state_matrix = state_matrix.T
    
    state_order = state_matrix.flatten()
    
    # Get values
    values = data.loc[state_order].values
    
    return values.reshape(state_matrix.shape)


def _insert_predictor(name, values, model_spec, log, standardise, update_prior):
    """
    Insert a predictor into a <glmSubstitutionModel> block. If a predictor with the same name
    already exists, its values will be replaced (with a warning).
    
    This function also increments the number of predictors (if needed), and the prior probability 
    for inclusion of any predictors will be updated accordingly to specify a 50% prior mass on no 
    predictors being included.
    
    Parameters
    ----------
    name : str
        Name of the predictor.
    values : numpy.ndarray
        Predictor values, in the form of a square matrix with the order of rows/columns matching 
        that of states defined in the XML.
    model_spec : xml.etree.ElementTree.Element
        The <glmSubstitutionModel> block to which the predictor should be added.
    update_prior : bool
        Whether to update the prior probability of predictor inclusion.
        
    Returns
    -------
    None
    """
    # Convert to string
    values = _apply_tranformations(values, log, standardise)
    values = _flatten_matrix(values)
    
    # Add predictor
    design_matrix = model_spec.glmModel.independentVariables.designMatrix
    existing_predictors = {p.get("id"): p for p in design_matrix.iterchildren("parameter")}
    
    if name in existing_predictors:
        warn(f"A predictor named '{name}' already exists. Values will be overwritten.",
             stacklevel=3, category=RuntimeWarning)
        existing_predictors[name].set("value", values)
    else:
        objectify.SubElement(design_matrix, "parameter", {"id": name, "value": values})
    
    # Update number of predictors
    predictor_count = design_matrix.countchildren()
    
    count_block = model_spec.rootFrequencies.frequencyModel.frequencies.parameter
    count_block.set("value", str(predictor_count))
    
    # Update prior
    if update_prior:
        # Get indicator id
        indicator = model_spec.glmModel.independentVariables.indicator
        indicator_id = indicator.parameter.get("id")
        
        # Find the <binomialLikelihood> prior element for this indicator
        root = model_spec.getparent()
        priors = root.mcmc.joint.prior
        
        for inclusion_prior in priors.iterchildren("binomialLikelihood"):
            indicator_ref = inclusion_prior.counts.parameter
            
            if indicator_ref.get("idref") == indicator_id:
                break
        else:
            raise ValueError("No <binomialLikelihood> prior element pointing to this GLM found.")
            
        # Set value
        # (calculation from https://github.com/beast-dev/beast-mcmc/blob/cf3d7370ca/src/dr/app/beauti/components/discrete/DiscreteTraitsComponentGenerator.java#L601)
        proportion = 1 - np.exp( np.log(0.5) / predictor_count )
        inclusion_prior.proportion.parameter.set("value", str(proportion))


# Public functions
def add_scalar_predictor(xml_root, data, 
                         datatype_id="location.dataType",
                         model_id="location.model", 
                         parameter_prefix="location",
                         log_transform=True,
                         standardise=True,
                         update_prior=True):
    """
    Add a scalar predictor to a BEAST xml. `xml_root` will be modified in-place.
    
    Parameters
    ----------
    xml_root : xml.etree.ElementTree.Element
        The root element of the xml file.
    data : pandas.DataFrame
        A DataFrame containing the predictor values. The index should refer to observed states
        (e.g. locations), and the first column should be the predictor values. The name of this 
        column will determine the predictor name. Any additional columns will be ignored.
    datatype_id : str
        ID attribute of the <generalDataType> block specifying the observed states to which this
        trait / GLM applies (default: "location.dataType").
    model_id : str
        ID attribute of the GLM model to which the predictor should be added (i.e., the ID of the 
        relevant <glmSubstitutionModel> in the XML; default: "location.model").
    parameter_prefix : str
        Prefix used for parameter names (default: "location", resulting in a coefficient parameter 
        named "location.[column_name]").
    log_transform : bool
        Whether to log-transform the predictor values (default: True).
    standardise : bool
        Whether to standardise the predictor values (default: True).
    update_prior : bool
        Whether to update the prior probability of predictor inclusion to adjust for the increase
        in the number of predictors (default: True).
        
    Returns
    -------
    None
    """
    # Get existing model specification
    model_spec, states = _parse_glm_specification(xml_root, model_id, datatype_id)
    
    # Check that the data contains all observed states
    if not set(states).issubset(data.index):
        raise ValueError(
            "Index of supplied predictor data does not contain all observed states listed in XML.")
    
    if not set(data.index).issubset(states):
        warn("Supplied predictor data contains states not listed in XML. These will be ignored.",
             stacklevel=2, category=RuntimeWarning)
    
    # Origin
    name = f"{parameter_prefix}.{data.columns[0]}_origin"
    value = _build_scalar_predictor(data, states, 0)
    _insert_predictor(name, value, model_spec,
                      log=log_transform,
                      standardise=standardise,
                      update_prior=update_prior)
    
    # Destination
    name = f"{parameter_prefix}.{data.columns[0]}_destination"
    value = _build_scalar_predictor(data, states, 1)
    _insert_predictor(name, value, model_spec,
                      log=log_transform, 
                      standardise=standardise,
                      update_prior=update_prior)


def add_matrix_predictor(xml_root, data, predictor_name,
                         datatype_id="location.dataType",
                         model_id="location.model", 
                         parameter_prefix="location",
                         log_transform=True,
                         standardise=True,
                         update_prior=True):
    """
    Add a matrix predictor to a BEAST xml. `xml_root` will be modified in-place.
    
    Parameters
    ----------
    xml_root : xml.etree.ElementTree.Element
        The root element of the xml file.
    data : pandas.DataFrame
        A DataFrame containing the predictor values. The index and column names should refer to 
        observed states (e.g. locations).
    predictor_name : str
        Name of the predictor. 
    datatype_id : str
        ID attribute of the <generalDataType> block specifying the observed states to which this
        trait / GLM applies (default: "location.dataType").
    model_id : str
        ID attribute of the GLM model to which the predictor should be added (i.e., the ID of the 
        relevant <glmSubstitutionModel> in the XML; default: "location.model").
    parameter_prefix : str
        Prefix used for parameter names (default: "location", resulting in a coefficient parameter 
        named "location.[predictor_name]").
    log_transform : bool
        Whether to log-transform the predictor values (default: True).
    standardise : bool
        Whether to standardise the predictor values (default: True).
    update_prior : bool
        Whether to update the prior probability of predictor inclusion to adjust for the increase
        in the number of predictors (default: True).
    
    Returns
    -------
    None
    """
    # Get existing model specification
    model_spec, states = _parse_glm_specification(xml_root, model_id, datatype_id)
    
    # Check that the data contains all observed states
    if len(data.shape) != 2:
        raise ValueError("Data should be 2-dimensional.")
    
    if data.shape[0] != data.shape[1]:
        raise ValueError("Data does not form a square matrix.")
    
    if not set(states).issubset(data.index):
        raise ValueError(
            "Index of supplied predictor data does not contain all observed states listed in XML.")
            
    if not set(states).issubset(data.columns):
        raise ValueError(
            "Columns of supplied predictor data does not contain all observed states listed in XML.")
    
    if not set(data.index).issubset(states):
        warn("Supplied predictor data contains states not listed in XML. These will be ignored.",
             stacklevel=2, category=RuntimeWarning)
    
    
    # Re-order to match states
    data = data.loc[states, states]
    
    # Add to XML
    name = f"{parameter_prefix}.{predictor_name}"
    values = data.values
    
    _insert_predictor(name, values, model_spec,
                      log=log_transform, 
                      standardise=standardise, 
                      update_prior=update_prior)


def add_predictor(xml_root, data,
                  predictor_name = None,
                  datatype_id="location.dataType",
                  model_id="location.model",
                  parameter_prefix="location",
                  log_transform=True,
                  standardise=True,
                  update_prior=True):
    """
    Add a predictor to a BEAST xml, using simple heuristics to determine whether the predictor
    is scalar or matrix.
    
    The following rules are applied (in order):
        1. Dataframes with an equal number of rows and columns will result in a call to 
        `add_matrix_predictor`.
        2. Dataframes with 2 columns will result in a call to `add_scalar_predictor`.
        3. If either of these  conditions can be satisfied by decreasing the number of columns by 1, 
        the first column is assumed to reflect observed states, and will be set as the index of 
        `data`, before repeating the above steps.
    
    `xml_root` will be modified in-place.
    
    See also: `add_scalar_predictor`, `add_matrix_predictor`.
    
    Parameters
    ----------
    xml_root : xml.etree.ElementTree.Element
        The root element of the xml file.
    data : pandas.DataFrame
        A DataFrame containing the predictor values. 
    predictor_name : str
        Name of the predictor. Ignored in the case of scalar predictors.
    datatype_id : str
        ID attribute of the <generalDataType> block specifying the observed states to which this
        trait / GLM applies (default: "location.dataType").
    model_id : str
        ID attribute of the GLM model to which the predictor should be added (i.e., the ID of the 
        relevant <glmSubstitutionModel> in the XML; default: "location.model").
    parameter_prefix : str
        Prefix used for parameter names (default: "location", resulting in a coefficient parameter 
        named "location.[predictor_name]").
    log_transform : bool
        Whether to log-transform the predictor values (default: True).
    standardise : bool
        Whether to standardise the predictor values (default: True).
    update_prior : bool
        Whether to update the prior probability of predictor inclusion to adjust for the increase
        in the number of predictors (default: True).
        
    Returns
    -------
    None
    """
    if len(data.shape) != 2:
        raise ValueError("Data should be 2-dimensional.")
        
    if data.shape[0] < 2:
        # Can't determine whether this is a scalar or matrix, but this makes no sense as a
        # predictor anyway
        raise ValueError("Data should contain at least 2 rows.")
    
    if data.shape[0] == data.shape[1]:
        add_matrix_predictor(xml_root, data, predictor_name, 
                             datatype_id, model_id, parameter_prefix, 
                             log_transform, standardise, update_prior)
                             
    elif data.shape[1] == 1:
        add_scalar_predictor(xml_root, data, 
                             datatype_id, model_id, parameter_prefix, 
                             log_transform, standardise, update_prior)
                             
    elif (data.shape[1] == data.shape[0] + 1) or (data.shape[1] == 2):
        warn("Data has an unexpected shape. Assuming first column is a list of observed states.",
             stacklevel=2, category=RuntimeWarning)
        
        data.set_index(data.columns[0], inplace=True)
        add_predictor(xml_root, data, 
                      predictor_name, datatype_id, model_id, parameter_prefix, 
                      log_transform, standardise, update_prior)
                      
    else:
        raise ValueError("Unexpected number of columns - predictor type cannot not be determined. "
                         "If this is a scalar feature and only the first column is relevant, use "
                         "add_scalar_predictor instead.")

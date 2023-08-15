# Parse IQ-TREE model and partition specifications

from warnings import warn
from re import split

from ..substitution_model import SubstitutionModel


def _parse_partition_string(partition_string):
    """
    Parse an IQ-TREE partition string, translating it to the indices of alignment columns included.
    
    Parameters
    ----------
    partition_string : str
        An IQ-TREE partition string to parse (see 
        http://www.iqtree.org/doc/Complex-Models#partition-models).
    
    Returns
    -------
    list of int
        The indices of alignment columns included in the partition.
    """
    # Parse components
    components = split("[ ]+", partition_string)
    indices = []
    
    for component in components:
        if "-" in component:
            # A range
            start, end = component.split("-")
            
            if end.endswith("\\3"):
                end = end.strip("\\3")
                step = 3
            else:
                step = 1
            
            indices.extend(range(int(start), int(end) + 1, step))
        else:
            # Single value
            indices.append(int(component))
    
    return indices


def _translate_model(model):
    """
    Translate an IQ-TREE model name to a BEAST model name.
    
    Parameters
    ----------
    model : str
        The IQ-TREE model name to translate.
    
    Returns
    -------
    (str, str)
        A tuple consisting of the BEAST model name and the frequency modifier implied by this model
        (either "equal", "unequal", or None).
    """
    # Models with equal base frequencies (based on http://www.iqtree.org/doc/Substitution-Models)
    equal_frequency_models = ["JC", "JC69", "K80", "K2P", "K81", "K3P", "TPM2", "TPM3", "SYM"]
    unequal_frequency_models = ["F81", "HKY", "HKY85", "TN", "TN93", "TIM", "TIM2", "TIM3", 
                                "TVM", "GTR"]
    
    translation_table = {
        "JC": "JC69",
        "K2P": "K80",
        "HKY85": "HKY",
        "TN": "TN93",
        "K81": "K3P"
    }
    
    # Check for frequency modifiers in the model name
    if model.endswith("e") or model in equal_frequency_models:
        frequency_modifier = "equal"
        model = model.rstrip("e")
    elif model.endswith("u") or model in unequal_frequency_models:
        frequency_modifier = "unequal"
        model = model.rstrip("u")
    else:
        frequency_modifier = None
    
    # Translate model name
    if model in SubstitutionModel.model_spec:
        # No change needed
        return model, frequency_modifier
    
    if model not in translation_table:
        # Input incorrect or model not implemented
        raise ValueError(f"Unrecognized model: {model}")
    
    return translation_table[model], frequency_modifier


def _parse_frequency_string(frequency_string):
    """
    Parse an IQ-TREE frequency string, returning the base frequencies implied.
    
    Parameters
    ----------
    frequency_string : str
        The IQ-TREE frequency string to parse.
    
    Returns
    -------
    str
        The base frequencies implied by this frequency string (either "empirical", "equal", or
        "estimated").
    """
    if frequency_string == "F":
        return "empirical"
    elif frequency_string == "FQ":
        return "equal"
    elif frequency_string == "FO":
        return "estimated"
    else:
        raise ValueError(f"Unrecognized frequency string: {frequency_string}")


def _parse_rate_variation(gamma_string):
    """
    Parse an IQ-TREE rate variation string ("+G" or "+R"), returning the number of rate variation
    categories required.
    
    Parameters
    ----------
    gamma_string : str
        The IQ-TREE rate variation string to parse.
    
    Returns
    -------
    int
        The number of rate variation categories required.
    """
    if not (gamma_string.startswith("G") or gamma_string.startswith("R")):
        raise ValueError(f"Unrecognized rate variation string: {gamma_string}")
    
    if gamma_string.startswith("R"):
        warn("Selected model uses the FreeRate generalisation, which is not supported by "
             "BEAST. Using Gamma-distributed rates instead.",
             RuntimeWarning, stacklevel=4)
    
    if gamma_string == "G" or gamma_string == "R":
        # Assume 4 categories when not specified
        return 4
    else:
        gamma_string = gamma_string.replace("G", "")
        gamma_string = gamma_string.replace("R", "")
        return int(gamma_string)


def _parse_model_string(model_string, id):
    """
    Parse an IQ-TREE model string, translating it to a SubstitutionModel object.
    
    Parameters
    ----------
    model_string : str
        An IQ-TREE model string to parse (see www.iqtree.org/doc/Substitution-Models).
    id : str
        The ID prefix to use for this substitution model.
    
    Returns
    -------
    SubstitutionModel
        The parsed substitution model.
    """
    # Parse components
    components = model_string.split("+")
    model = components[0].strip()
    model, frequency_modifier = _translate_model(model)
    
    # Defaults (might be updated below)
    if frequency_modifier == "equal":
        frequencies = "equal"
    elif frequency_modifier == "unequal":
        # IQ-TREE uses empirical frequencies by default for models with unequal frequencies
        frequencies = "empirical"
    
    invariant_sites = False
    gamma = None
    
    # Check for other modifiers (+X)
    if len(components) > 1:
        for modifier in components[1:]:
            if modifier.startswith("F"):
                frequencies = _parse_frequency_string(modifier)
            elif modifier.startswith("G") or modifier.startswith("R"):
                gamma = _parse_rate_variation(modifier)
            elif modifier == "I":
                invariant_sites = True
            else:
                raise ValueError(f"Unrecognized model modifier: {modifier}")
    
    # Check for conflicting modifiers
    if frequency_modifier == "equal" and frequencies != "equal":
        raise ValueError("Model name implies equal frequencies, but frequencies are not equal in "
                         f"model string '{model_string}'.")
    elif frequency_modifier == "unequal" and frequencies == "equal":
        raise ValueError("Model name implies unequal frequencies, but frequencies are equal in "
                         f"model string '{model_string}'.")
    
    return SubstitutionModel(id_prefix=id, 
                             frequencies=frequencies,
                             model=model, 
                             gamma=gamma, 
                             prop_invariant=invariant_sites)


def read_model_test(path):
    """
    Read the result file of a IQ-TREE model test (*.best_scheme.nex).
    
    Note: only DNA models are currently supported.
    
    Parameters
    ----------
    path : str
        Path to the model test result file, in nexus format.
    
    Returns
    -------
    (dict, dict)
        A tuple of two dictionaries. The first maps alignment names to substitution models, and the 
        second maps alignment names to partition definitions.
    """
    models = {}
    partitions = {}

    in_partition_block = False
    in_model_block = False

    with open(path, "r") as f:
        for line in f:
            line_uppercase = line.upper()

            if line_uppercase.startswith("BEGIN SETS;"):
                # Next lines will be partition definitions
                in_partition_block = True
                in_model_block = False

            elif in_partition_block and line_uppercase.strip().startswith("CHARPARTITION"):
                # Next lines will be model definitions
                in_partition_block = False
                in_model_block = True

            elif line_uppercase.startswith("END;"):
                # End of partition definitions, so we can stop reading
                break

            elif in_partition_block:
                if line_uppercase.strip().startswith("CHARSET"):
                    name, definition = line.split("=")
                    name = name.replace("charset", "").strip()
                    definition = definition.replace(";", "").strip()

                    partitions[name] = _parse_partition_string(definition)
                else:
                    warn(f"Invalid line in partition definitions ignored: {line}")

            elif in_model_block:
                model, name = line.split(":")
                model = model.strip()

                name = name.replace(",", "")
                name = name.replace(";", "")
                name = name.strip()

                models[name] = _parse_model_string(model, id=name)
                
    return models, partitions

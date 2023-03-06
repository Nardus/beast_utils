# A class describing a full substitution model specification

from lxml import objectify, etree
from pkgutil import get_data

from ..io import from_string
from ..templating import update_from_template


class SubstitutionModel(dict):
    """
    A substitution model specification which can be translated to BEAST XML. 
    
    All identifiers will share a common prefix name, which is assumed to also be the name
    of the alignment that this model applies to.
    """
    model_spec = {
        "JC69": "templates/jc69.xml",
        "F81": "templates/f81.xml",
        "K80": "templates/k80.xml",
        "HKY": "templates/hky.xml",
        "TN93": "templates/tn93.xml",
        "K3P": "templates/k3p.xml",
        "TIM": "templates/tim.xml",
        "TVM": "templates/tvm.xml",
        "SYM": "templates/sym.xml",
        "GTR": "templates/gtr.xml",
    }
    
    modifiers = {
        "equal": "templates/equal_frequencies.xml",
        "estimated": "templates/estimated_frequencies.xml",
        "gamma": "templates/gamma.xml",
        "prop_invariant": "templates/proportion_invariant.xml"
    }
    
    def __init__(self, id_prefix, model, frequencies="estimated", gamma=None, prop_invariant=False):
        """       
        Parameters
        ----------
        id_prefix : str
            A prefix to use for all IDs in the XML
        model : str
            The model to use. Must be one of the keys in `model_spec`.
        frequencies : str
            How to estimate base frequencies. Must be one of "estimated", "empirical", or "equal".
        gamma : int
            The number of gamma rate categories to use. If None, no rate variation is used.
        prop_invariant : bool
            Whether to use a proportion of invariant sites.
        """
        self.id_prefix = id_prefix
        self.set_model(model)
        self.set_frequencies(frequencies)
        
        if gamma is not None:
            self.set_gamma(gamma)
        
        self.set_prop_invariant(prop_invariant)
    
    
    def set_model(self, model):
        if model not in self.model_spec.keys():
            raise ValueError(f"Unknown model: {model}")
        
        self.model = model
    
    
    def set_frequencies(self, frequencies):
        valid_vals = ["estimated", "empirical", "equal"]
        
        if frequencies not in valid_vals:
            raise ValueError(f"Invalid value - must be one of {valid_vals}")
        
        self.frequencies = frequencies
    
    
    def set_gamma(self, gamma):
        if not isinstance(gamma, int):
            raise ValueError("gamma must be an integer value.")
        if not gamma > 0:
            raise ValueError("gamma must be greater than 0.")
        
        self.gamma = gamma
    
    
    def set_prop_invariant(self, prop_invariant):
        if not isinstance(prop_invariant, bool):
            raise ValueError("prop_invariant must be boolean.")
            
        self.prop_invariant = prop_invariant
    
    
    def _update_from_internal_template(self, xml_tree, template_path):
        """
        Update an XML tree with a template from the internal templates directory.
        
        Parameters
        ----------
        xml_tree : lxml.etree.ElementTree
            The XML tree to update.
        template_path : str
            The path to the template file, relative to this package.
        """
        template_string = get_data(__name__, template_path)
        template_tree = from_string(template_string)

        return update_from_template(xml_tree, template_tree)
    
    
    def update_model_name(self, model_tree, name_prefix,
                          protected_ids=["operators", "mcmc", "joint", "prior",
                                         "fileLog", "screenLog"]):
        """
        Update the name of the substitution model XML. This updates all id and idref attributes, 
        unless the current value of the attribute is listed in `protected_ids`.
        
        `model_tree` is modified in place.
        
        Parameters
        ----------
        model_tree : lxml.etree.ElementTree
            The substitution model XML tree.
        name_prefix : str
            The prefix to use for all elements in the xml.
        
        Returns
        -------
        None
        """
        # Don't double prefix bare (e.g. "codon3"), which refers to the alignment
        protected_ids.append(self.id_prefix)
        
        # Update recursively
        if isinstance(model_tree, etree._ElementTree):
            # Top level call (i.e. no recursion yet)
            self.id_prefix = name_prefix
            model_tree = model_tree.getroot()
        
        for element in model_tree.getchildren():
            if "id" in element.attrib:
                cur_id = element.attrib["id"]

                if cur_id not in protected_ids:
                    element.attrib["id"] = f"{name_prefix}.{cur_id}"

            if "idref" in element.attrib:
                cur_id = element.attrib["idref"]

                if cur_id not in protected_ids:
                    element.attrib["idref"] = f"{name_prefix}.{cur_id}"

            if element.countchildren() > 0:
                self.update_model_name(element, name_prefix, protected_ids)

        return None
    
    
    def _update_frequency_estimation(self, model_tree):
        """
        Update the frequency estimation method for the substitution model xml to match 
        self.frequencies.
        
        `model_tree` is modified in place
        
        Note: in most cases, this function will *not* work when called externally, as it assumes
        parameter ids have not yet been prefixed with the model name (not the case once `build_xml`
        has been called).
        
        Depending on the model, this function may have no effect - models which by definition have 
        unequal base frequencies (e.g. HKY) will have empirical frequencies defined as default 
        already. Setting frequencies to empirical does nothing in this case.
        
        Parameters
        ----------
        model_tree : lxml.etree.ElementTree
            The substitution model XML tree.
            
        Returns
        -------
        None
        """
        # Frequency values
        freq_param = model_tree.find(
            "/*/frequencies/frequencyModel/frequencies/parameter[@id='frequencies']"
        )
        
        if freq_param is None:
            raise RuntimeError("Could not find frequencies parameter in model XML. Ensure the "
                               "model's frequency parameter has id='frequencies' "
                               "(and no prefix/suffix).")
        
        if self.frequencies in ["equal", "estimated"]:
            # Set initial values for frequencies
            freq_param.attrib["value"] = "0.25 0.25 0.25 0.25"
            
            if "dimension" in freq_param.attrib:
                freq_param.attrib.pop("dimension")
        else:
            # Don't set initial values for frequencies, forcing BEAST to get it from the data
            # during initialisation
            if "value" in freq_param.attrib:
                freq_param.attrib.pop("value")
                
            # Set dimension instead
            freq_param.attrib["dimension"] = "4"
        
        # For empirical frequencies, also need a reference to the source alignment
        alignment = model_tree.find("/*/frequencies/frequencyModel/alignment")
        
        if self.frequencies == "empirical":
            # Add or update alignment reference
            if alignment is None:
                freq_model = model_tree.find("/*/frequencies/frequencyModel")
                objectify.SubElement(freq_model, "alignment", {"idref": self.id_prefix})
            else:
                alignment.attrib["idref"] = self.id_prefix
        else:
            # Remove alignment reference
            if alignment is not None:
                alignment.getparent().remove(alignment)
            
        
        # Operators and priors
        if self.frequencies in ["equal", "empirical"]:
            # Ensure there's no operator modifying frequencies after initialisation
            operator_params = model_tree.iterfind("operators/*/parameter[@idref='frequencies']")
            
            if operator_params is not None:
                for op in operator_params:
                    # Remove entire operator, not just the <parameter> enclosed by it
                    operator = op.getparent()
                    operator.getparent().remove(operator)
            
            # Remove prior on frequencies (if present)
            prior_params = model_tree.iterfind("mcmc/joint/prior/*/parameter[@idref='frequencies']")
            
            if prior_params is not None:
                for pp in prior_params:
                    prior = pp.getparent()
                    prior.getparent().remove(prior)
            
        else:
            # Insert everything required to estimate frequencies during MCMC
            self._update_from_internal_template(model_tree, self.modifiers["estimated"])
            
        return None
    
    
    def build_xml(self):
        """
        Build an XML representation of this substitution model.
        
        Returns
        -------
        lxml.etree.ElementTree
            The XML tree.
        """
        base_xml = self.model_spec[self.model]
        base_tree = from_string(get_data(__name__, base_xml))
        
        # Add modifiers
        self._update_frequency_estimation(base_tree)
        
        if self.gamma is not None:
            self._update_from_internal_template(base_tree, self.modifiers["gamma"])
            
            if self.gamma != 4:
                gamma_element = base_tree.find("siteModel/gammaShape")
                gamma_element.attrib["gammaCategories"] = str(self.gamma)
            
        if self.prop_invariant:
            self._update_from_internal_template(base_tree, self.modifiers["prop_invariant"])
        
        # Rename IDs to avoid conflicts when multiple models are used
        self.update_model_name(base_tree, self.id_prefix)
        
        return base_tree
        
    def insert_xml(self, xml_tree, tree_data_likelihood_id="treeLikelihood"):
        """
        Insert the XML representation of this substitution model into an existing XML tree.
        
        Parameters
        ----------
        xml_tree : lxml.etree.ElementTree
            The existing XML tree.
        tree_data_likelihood_id : str, optional
            The id of the <treeDataLikelihood> element to register the model with.
        
        Returns
        -------
        lxml.etree.ElementTree
            The updated XML tree.
        """
        # Insert model XML
        model_xml = self.build_xml()
        xml_tree = update_from_template(xml_tree, model_xml)
        
        # Register model in treeDataLikelihood
        tree_likelihood = xml_tree.find(f"/treeDataLikelihood[@id='{tree_data_likelihood_id}']")

        if tree_likelihood is None:
            raise ValueError("Could not find <treeDataLikelihood> element with id "
                             f"'{tree_data_likelihood_id}'.")
        
        partition = tree_likelihood.find(f"partition/patterns[@idref='{self.id_prefix}.patterns']")
        
        if partition is None:
            raise ValueError("Could not find a partition for this model's alignment. Ensure the "
                             f"alignment's site patterns element has id '{self.id_prefix}.patterns' "
                             "and is registered in the <treeDataLikelihood> element.")
        
        partition = partition.getparent()
        objectify.SubElement(partition, "siteModel", {"idref": f"{self.id_prefix}.siteModel"})
        
        # Ensure treeDataLikelihood occurs after the siteModel it references
        xml_root = xml_tree.getroot()
        siteModel = xml_tree.find(f"/siteModel[@id='{self.id_prefix}.siteModel']")
        
        xml_root.remove(tree_likelihood)
        xml_root.insert(xml_root.index(siteModel) + 1, tree_likelihood)
        
        return xml_tree
    
    
    def __str__(self):
        modifiers = ""
        
        if self.gamma is not None:
            modifiers += f"+G{self.gamma}"
            
        if self.prop_invariant:
            modifiers += "+I"
        
        return f"{self.model}{modifiers} ({self.frequencies} frequencies)"
    
    def __repr__(self):
        return f"SubstitutionModel[{str(self)}]"

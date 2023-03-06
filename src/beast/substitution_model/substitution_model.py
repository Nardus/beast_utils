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
    
    
    def _get_partition_sizes(self, xml_tree):
        """
        Get the number of partition characters associated with each siteModel in xml_tree.
        
        Parameters
        ----------
        xml_tree : lxml.etree.ElementTree
            The substitution model XML tree.
        
        Returns
        -------
        dict
            A dictionary mapping site model ids to the number of partition characters.
        """
        # Get the alignment linked to each site model
        # - treeDataLikelihood links site models to patterns, which in turn points to alignments
        # - since partitions are added separately from (and before) models, some partitions may 
        #   not have site models yet - only including those that do (implying the substitution 
        #   model has been added already)
        alignment_names = {}
        
        for partition in xml_tree.findall("/treeDataLikelihood/partition"):
            siteModel = partition.find("siteModel")
            
            if siteModel is not None:
                sitemodel_id = siteModel.get("idref")
                pattern_id = partition.find("patterns").get("idref")

                patterns = xml_tree.find(f"/patterns[@id='{pattern_id}']")
                alignment_id = patterns.find("alignment").get("idref")

                alignment_names[sitemodel_id] = alignment_id

        # Get the number of characters in each alignment
        alignment_sites = {}

        for sitemodel_id, alignment_id in alignment_names.items():
            alignment = xml_tree.find(f"/alignment[@id='{alignment_id}']")

            first_seq_element = alignment.getchildren()[0]
            first_sequence = first_seq_element.getchildren()[-1].tail
            first_sequence = first_sequence.lstrip().rstrip()

            alignment_sites[sitemodel_id] = len(first_sequence)
        
        return alignment_sites
    
    
    def _convert_mu_to_nu(self, xml_tree, sitemodel_id, n_partitions):
        """
        Convert a siteModel's relative rate parameters to the nu-based representation.
        
        If the relative rate parameter does not in ".mu", no action is taken.
        
        Parameters
        ----------
        xml_tree : lxml.etree.ElementTree
            The XML tree to modify.
        sitemodel_id : str
            The ID parameter of siteModel in xml_tree.
        n_partitions : int
            Number of partitions present in this XML.
        
        Returns
        -------
        str
            The name of the nu param (or the original parameter name if no action was taken).
        """
        xml_root = xml_tree.getroot()
        
        sitemodel = xml_tree.find(f"/siteModel[@id='{sitemodel_id}']")
        relative_rate = sitemodel.find("relativeRate")

        # Only update if needed
        parameter = relative_rate.find("parameter")
        old_id = parameter.get("id")
        
        if old_id.endswith(".mu"):
            # Replace mu parameter with nu
            new_id = f"{sitemodel_id}.nu"
            parameter.set("id", new_id)
            parameter.set("value", str(1 / n_partitions))
            parameter.set("lower", "0.0")
            parameter.set("upper", "1.0")

            # Calculate mu statistic from nu
            mu_statistic = xml_root.makeelement("statistic", {"id": old_id, "name": "mu"})
            objectify.SubElement(mu_statistic, "siteModel", idref=sitemodel_id)
            xml_root.insert(xml_root.index(sitemodel) + 1, mu_statistic)
            
            # Log both parameters
            log = xml_tree.find("/mcmc/log[@id='fileLog']")
            old_mu_log = log.find(f"parameter[@idref='{old_id}']")
            
            if old_mu_log is not None:
                log.remove(old_mu_log)
            
            objectify.SubElement(log, "statistic", {"idref": old_id})
            objectify.SubElement(log, "parameter", {"idref": new_id})
            
            return new_id
            
        else:
            return old_id
    
    
    def _update_site_model_relative_rates(self, xml_tree):
        """
        Update all site model relative rate parameters, using the new per-partition
        ("nu") parameterization with a Dirchlet prior.
        
        xml_tree is modified in place.
        
        Parameters
        ----------
        xml_tree : lxml.etree.ElementTree
            The XML tree to modify.
        
        Returns
        -------
        None
        """
        xml_root = xml_tree.getroot()
        alignment_sites = self._get_partition_sizes(xml_tree)
        
        # No need for relative rates if there's only one partition
        n_partitions = len(alignment_sites)
        
        if n_partitions == 1:
            return None
        
        # Modify all sequence-related site models to reflect the current number of 
        # relative rate params
        total_sites = sum(alignment_sites.values())
        nu_ids = []
        
        for sitemodel_id, cur_sites in alignment_sites.items():
            # Convert to nu-based representation if needed
            id = self._convert_mu_to_nu(xml_tree, sitemodel_id, n_partitions)
            nu_ids.append(id)
            
            # Set weight relative to partition size
            rel_weight = total_sites / cur_sites
            
            sitemodel = xml_tree.find(f"/siteModel[@id='{sitemodel_id}']")
            relative_rate = sitemodel.find("relativeRate")
            relative_rate.set("weight", str(rel_weight))
            
        # Add the "allNus" compound parameter if needed      
        compound_param = xml_tree.find("/compoundParameter[@id='allNus']")
        
        if compound_param is None:
            compound_param = xml_root.makeelement("compoundParameter", {"id": "allNus"})
            
            # Insert before the tree likelihood
            tree_likelihood = xml_tree.find("treeDataLikelihood")
            xml_root.insert(xml_root.index(tree_likelihood) - 1, compound_param)
            
            # Add to log
            log = xml_tree.find("/mcmc/log[@id='fileLog']")
            objectify.SubElement(log, "compoundParameter", {"idref": "allNus"})
        
        # Add any missing nu parameters to allNus
        known_nus = [c.get("idref") for c in compound_param.getchildren()]
        add_nus = set(nu_ids) - set(known_nus)
        
        for nu in add_nus:
            objectify.SubElement(compound_param, "parameter", idref=nu)
        
        # Add operator
        nu_operator = xml_tree.find("/operators/*/parameter[@idref='allNus']")
        
        if nu_operator is None:
            operators = xml_tree.find("/operators")
            op = objectify.SubElement(operators, "deltaExchange", delta="0.01", weight="3")
            objectify.SubElement(op, "parameter", idref="allNus")
            
        # Add prior
        nu_prior = xml_tree.find("/mcmc/joint/prior/*/parameter[@idref='allNus']")
        
        if nu_prior is None:
            priors = xml_tree.find("/mcmc/joint/prior")
            pr = objectify.SubElement(priors, "dirichletPrior", alpha="1.0", sumsTo="1.0")
            objectify.SubElement(pr, "parameter", idref="allNus")
    
    
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
        
    def insert_xml(self, xml_tree, tree_data_likelihood_id="treeLikelihood", 
                   new_parameterization=False):
        """
        Insert the XML representation of this substitution model into an existing XML tree.
        
        Parameters
        ----------
        xml_tree : lxml.etree.ElementTree
            The existing XML tree.
        tree_data_likelihood_id : str, optional
            The id of the <treeDataLikelihood> element to register the model with.
        new_parameterization : bool, optional
            If True, use the new relative rate parameterization introduced in BEAST 1.10
            (see https://groups.google.com/g/beast-users/c/FWN7lGJ75Wk/m/YQEhZx4HAwAJ).
        
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
        
        # Update relative rate parameters
        if new_parameterization:
            self._update_site_model_relative_rates(xml_tree)
        
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

#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# xclim documentation build configuration file, created by
# sphinx-quickstart on Fri Jun  9 13:47:02 2017.
#
# This file is execfile()d with the current directory set to its
# containing dir.
#
# Note that not all possible configuration values are present in this
# autogenerated file.
#
# All configuration values have a default; values that are commented out
# serve to show the default.
import os
import sys

import guzzle_sphinx_theme

import xclim
import xclim.utils as xcu

# If extensions (or modules to document with autodoc) are in another
# directory, add these directories to sys.path here. If the directory is
# relative to the documentation root, use os.path.abspath to make it
# absolute, like shown here.
#

sys.path.insert(0, os.path.abspath(".."))
sys.path.insert(0, os.path.abspath("."))


def _get_indicators(modules):
    """For all modules or classes listed, return the children that are instances of xclim.utils.Indicator.

    modules : sequence
      Sequence of modules to inspect.
    """
    out = []
    for obj in modules:
        for key, val in obj.__dict__.items():
            if isinstance(val, xcu.Indicator):
                out.append(val)

    return out


def _indicator_table():
    """Return a sequence of dicts storing metadata about all available indices."""
    import xclim.atmos as atmos
    import inspect

    inds = _get_indicators([atmos])
    table = []
    for ind in inds:
        # Apply default values
        args = {
            name: p.default
            for (name, p) in ind._sig.parameters.items()
            if p.default != inspect._empty
        }
        table.append(ind.json(args))
    return table


indicators = _indicator_table()

# -- General configuration ---------------------------------------------

# If your documentation needs a minimal Sphinx version, state it here.
#
# needs_sphinx = '1.0'

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom ones.
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.viewcode",
    "sphinx.ext.mathjax",
    "sphinx.ext.napoleon",
    "sphinx.ext.coverage",
    "sphinx.ext.todo",
    "rstjinja",
    "nbsphinx",
    "guzzle_sphinx_theme",
    "IPython.sphinxext.ipython_console_highlighting",
]

# To avoid having to install these and burst memory limit on ReadTheDocs.
autodoc_mock_imports = [
    "numpy",
    "scipy",
    "xarray",
    "fiona",
    "rasterio",
    "shapely",
    "osgeo",
    "geopandas",
    "pandas",
    "netCDF4",
    "cftime",
    "dask",
    "bottleneck",
    "pyproj",
    "scikit-learn",
    "pint",
    "boltons",
]

napoleon_numpy_docstring = True
napoleon_use_rtype = False
napoleon_use_param = False
napoleon_use_ivar = True

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# The suffix(es) of source filenames.
# You can specify multiple suffix as a list of string:
#
# source_suffix = ['.rst', '.md']
source_suffix = [".rst", ".ipynb"]

# The master toctree document.
master_doc = "index"

# General information about the project.
project = "xclim"
copyright = "2018, Ouranos Inc., Travis Logan, and contributors"
author = "Travis Logan"

# The version info for the project you're documenting, acts as replacement
# for |version| and |release|, also used in various other places throughout
# the built documents.
#
# The short X.Y version.
version = xclim.__version__
# The full version, including alpha/beta/rc tags.
release = xclim.__version__

# The language for content autogenerated by Sphinx. Refer to documentation
# for a list of supported languages.
#
# This is also used if you do content translation via gettext catalogs.
# Usually you set "language" from the command line for these cases.
language = None

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This patterns also effect to html_static_path and html_extra_path
exclude_patterns = [
    "_build",
    "Thumbs.db",
    ".DS_Store",
    "notebooks/xclim_training",
    "**.ipynb_checkpoints",
]

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = "sphinx"

# If true, `todo` and `todoList` produce output, else they produce nothing.
todo_include_todos = True

# -- Options for HTML output -------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_title = "XClim Official Documentation"
html_short_title = "XClim"

html_theme_path = guzzle_sphinx_theme.html_theme_path()
html_theme = "guzzle_sphinx_theme"  # 'alabaster

html_context = {"indicators": indicators}

# Theme options are theme-specific and customize the look and feel of a
# theme further.  For a list of options available for each theme, see the
# documentation.
#
html_theme_options = {
    "project_nav_name": "XClim {}".format(xclim.__version__),
    "homepage": "index",
}

html_sidebars = {
    "**": ["logo-text.html", "globaltoc.html", "localtoc.html", "searchbox.html"]
}

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ["_static"]

# -- Options for HTMLHelp output ---------------------------------------

# Output file base name for HTML help builder.
htmlhelp_basename = "xclimdoc"

# -- Options for LaTeX output ------------------------------------------

latex_elements = {
    # The paper size ('letterpaper' or 'a4paper').
    #
    # 'papersize': 'letterpaper',
    # The font size ('10pt', '11pt' or '12pt').
    #
    # 'pointsize': '10pt',
    # Additional stuff for the LaTeX preamble.
    #
    # 'preamble': r"""
    # \renewcommand{\v}[1]{\mathbf{#1}}
    # """,
    # Latex figure (float) alignment
    #
    # 'figure_align': 'htbp',
}

# Grouping the document tree into LaTeX files. List of tuples
# (source start file, target name, title, author, documentclass
# [howto, manual, or own class]).
latex_documents = [
    (master_doc, "xclim.tex", "xclim Documentation", "Travis Logan", "manual")
]

# -- Options for manual page output ------------------------------------

# One entry per manual page. List of tuples
# (source start file, name, description, authors, manual section).
man_pages = [(master_doc, "xclim", "xclim Documentation", [author], 1)]

# -- Options for Texinfo output ----------------------------------------

# Grouping the document tree into Texinfo files. List of tuples
# (source start file, target name, title, author,
#  dir menu entry, description, category)
texinfo_documents = [
    (
        master_doc,
        "xclim",
        "xclim Documentation",
        author,
        "xclim",
        "One line description of project.",
        "Miscellaneous",
    )
]

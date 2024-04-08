# Usage:
#   bokeh serve --show bokeh-server.py

from base64 import b64decode
import io
import pandas as pd

from bokeh.layouts import column
from bokeh.models import FileInput, Select
from bokeh.plotting import figure, curdoc

ROOT_LAYOUT = 'root'
DROPDOWN_LAYOUT_NAME = 'dropdown'
BAR_PLOT_NAME = 'plot1'


def load_file(attr, _old_value, new_value):
    global columns
    assert attr == 'value'

    print('Loading metadata...')
    file = io.BytesIO(b64decode(new_value))
    metadata = pd.read_csv(file, delimiter='\t')
    print('Successfully loaded metadata.')

    columns = metadata.columns.tolist()

    # This isn't great - a callback within a callback. Doing this because I
    # can't figure out how to dynamically update the same layout. Replacing it
    # entirely as a workaround, which necessitates nested callback to retain the
    # user input sequence.
    def update_plots(attr, _old_value, column):
        assert attr == 'value'

        value_counts = metadata[column].value_counts()
        columns = list(value_counts.index)
        counts = list(value_counts)

        p = figure(x_range=columns, height=350, title="Column summary", name=BAR_PLOT_NAME)
        p.vbar(x=columns, top=counts, width=0.9)

        replace_layout(BAR_PLOT_NAME, p)


    dropdown = Select(title='Select Column', options=[(col, col) for col in columns], name=DROPDOWN_LAYOUT_NAME)
    dropdown.on_change('value', update_plots)
    replace_layout(DROPDOWN_LAYOUT_NAME, dropdown)


def replace_layout(name, new_plot):
    sublayouts = curdoc().get_model_by_name(ROOT_LAYOUT).children
    old_layout = curdoc().get_model_by_name(name)
    for i, layout in enumerate(sublayouts):
        if layout == old_layout:
            sublayouts[i] = new_plot


file_input = FileInput(title="Select files:", accept=".tsv")
file_input.on_change('value', load_file)
dropdown = Select(title='Select Column (select metadata first)', options=[], name=DROPDOWN_LAYOUT_NAME)
p = figure(name=BAR_PLOT_NAME, height=350)

curdoc().add_root(column(file_input, dropdown, p, name=ROOT_LAYOUT))

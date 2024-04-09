# Usage:
#   bokeh serve --show bokeh-server.py

from base64 import b64decode
from datetime import datetime
import io
import pandas as pd

from bokeh.layouts import column
from bokeh.models import FileInput, Select
from bokeh.palettes import Category20
from bokeh.plotting import figure, curdoc

ROOT_LAYOUT = 'root'
DROPDOWN_LAYOUT_NAME = 'dropdown'
BAR_PLOT_NAME = 'plot1'
CATEGORY_LIMIT = 19


def load_file(attr, _old_value, new_value):
    assert attr == 'value'

    print('Loading metadata...')
    file = io.BytesIO(b64decode(new_value))
    metadata = pd.read_csv(file, delimiter='\t')
    print('Successfully loaded metadata.')

    columns = metadata.columns.tolist()

    def dropdown_callback(attr, _old_value, column):
        assert attr == 'value'
        update_plots(metadata, column)

    dropdown = Select(title='Select Column', options=[(col, col) for col in columns], name=DROPDOWN_LAYOUT_NAME)
    dropdown.on_change('value', dropdown_callback)
    replace_layout(DROPDOWN_LAYOUT_NAME, dropdown)


def sort_months(months):    
    # sort YYYY-MM strings - a bit hacky
    datetime_objects = [datetime.strptime(month, "%Y-%m") for month in months]
    sorted_datetime_objects = sorted(datetime_objects)
    return [dt.strftime("%Y-%m") for dt in sorted_datetime_objects]

def update_plots(metadata, column):
    metadata['date_month'] = pd.to_datetime(metadata['date']).dt.strftime("%Y-%m")
    months = sort_months(metadata['date_month'].unique().tolist())
    

    top_column_values = set(metadata[column].value_counts(sort=True).index[:CATEGORY_LIMIT])
    metadata['category_adj'] = metadata[column].apply(lambda v: v if v in top_column_values else 'other')
    column_values = metadata['category_adj'].unique().tolist()

    data = {
        'time': months
    }
    for category in column_values:
        data[category] = [len(metadata.query(f"{'category_adj'} == {category!r} & date_month == {month!r}")) for month in months]

    colors = Category20[len(column_values)]

    p = figure(x_range=months, height=350, title="distribution over time (months)", toolbar_location=None, tools="hover", tooltips="$name @time: @$name", name=BAR_PLOT_NAME)
    p.vbar_stack(column_values, x='time', source=data, color=colors, legend_label=column_values)

    p.y_range.start = 0
    p.x_range.range_padding = 0.1
    p.xgrid.grid_line_color = None
    p.axis.minor_tick_line_color = None
    p.outline_line_color = None
    p.legend.location = "top_left"
    p.legend.orientation = "horizontal"

    replace_layout(BAR_PLOT_NAME, p)


def replace_layout(name, new_layout):
    sublayouts = curdoc().get_model_by_name(ROOT_LAYOUT).children
    old_layout = curdoc().get_model_by_name(name)
    for i, layout in enumerate(sublayouts):
        if layout == old_layout:
            sublayouts[i] = new_layout


file_input = FileInput(title="Select files:", accept=".tsv")
file_input.on_change('value', load_file)
dropdown = Select(title='Select Column (select metadata first)', options=[], name=DROPDOWN_LAYOUT_NAME)
p = figure(name=BAR_PLOT_NAME, height=350)

curdoc().add_root(column(file_input, dropdown, p, name=ROOT_LAYOUT))

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
COLUMN_SELECTOR_LAYOUT_NAME = 'column_selector'
BAR_PLOT_NAME = 'plot1'
CATEGORY_LIMIT = 19


def load_file(attr, _old_value, new_value):
    assert attr == 'value'

    print('Loading metadata...')
    file = io.BytesIO(b64decode(new_value))
    metadata = pd.read_csv(file, delimiter='\t')
    print('Successfully loaded metadata.')
    plot_per_month(metadata)

    unique_value_counts = [(col, metadata[col].nunique()) for col in metadata]

    # Remove columns that have less than 2 and more than 100 unique values
    unique_value_counts = [(col, n) for col, n in unique_value_counts if 2 <= n <= 100]
    sorted_counts = sorted(unique_value_counts, key=lambda x: x[1])

    def column_selector_callback(attr, _old_value, column):
        assert attr == 'value'
        plot_stacked_per_month(metadata, column)

    column_selector = Select(
        name=COLUMN_SELECTOR_LAYOUT_NAME,
        title='Select column',
        options=[(col, f"{col} (n={count})") for col, count in sorted_counts],
    )
    column_selector.on_change('value', column_selector_callback)
    replace_layout(COLUMN_SELECTOR_LAYOUT_NAME, column_selector)


def sort_months(months):
    # sort YYYY-MM strings - a bit hacky
    datetime_objects = [datetime.strptime(month, "%Y-%m") for month in months]
    sorted_datetime_objects = sorted(datetime_objects)
    return [dt.strftime("%Y-%m") for dt in sorted_datetime_objects]


def plot_per_month(metadata):
    metadata['date_month'] = pd.to_datetime(metadata['date']).dt.strftime("%Y-%m")
    months = sort_months(metadata['date_month'].unique().tolist())

    count_by_month = metadata['date_month'].value_counts(sort=False).to_dict()
    counts = [count_by_month[month] for month in months]

    p = figure(name=BAR_PLOT_NAME,
        x_range=months, height=350,
        title="distribution over time (months)",
        toolbar_location="below", tools = "pan,wheel_zoom,box_zoom,reset,hover",
        tooltips="@x (n=@top)",
        )
    p.vbar(x=months, top=counts)

    p.y_range.start = 0
    p.x_range.range_padding = 0.1
    p.xgrid.grid_line_color = None
    p.xaxis.major_label_orientation = "vertical"
    p.axis.minor_tick_line_color = None
    p.outline_line_color = None

    replace_layout(BAR_PLOT_NAME, p)


def plot_stacked_per_month(metadata, column):
    metadata['date_month'] = pd.to_datetime(metadata['date']).dt.strftime("%Y-%m")
    months = sort_months(metadata['date_month'].unique().tolist())

    # Convert column to string to ensure categorical
    metadata[column] = metadata[column].astype(str)
    top_column_values = set(metadata[column].value_counts(sort=True, ascending=False).index[:CATEGORY_LIMIT])
    metadata['category_adj'] = metadata[column].apply(lambda v: v if v in top_column_values else 'other')
    column_values = metadata['category_adj'].unique().tolist()

    data = {
        'time': months
    }
    for category in column_values:
        data[category] = [len(metadata.query(f"{'category_adj'} == {category!r} & date_month == {month!r}")) for month in months]

    colors = Category20[len(column_values)]

    p = figure(name=BAR_PLOT_NAME,
        x_range=months, height=350,
        title="distribution over time (months)",
        toolbar_location="below", tools = "pan,wheel_zoom,box_zoom,reset,hover",
        tooltips="$name @time (n=@$name)",
        )
    p.vbar_stack(column_values, x='time', source=data, color=colors, legend_label=column_values)

    p.y_range.start = 0
    p.x_range.range_padding = 0.1
    p.xgrid.grid_line_color = None
    p.xaxis.major_label_orientation = "vertical"
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
column_selector = Select(
    name=COLUMN_SELECTOR_LAYOUT_NAME,
    title='Select column (select metadata first)',
    options=[],
    disabled=True,
)
p = figure(name=BAR_PLOT_NAME, height=350)

curdoc().add_root(column(file_input, column_selector, p, name=ROOT_LAYOUT))

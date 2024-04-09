# Usage:
#   bokeh serve --show bokeh-server.py

from base64 import b64decode
from datetime import datetime
import io
import pandas as pd

from bokeh.layouts import column, row
from bokeh.models import FileInput, Select, Div
from bokeh.palettes import Category20
from bokeh.plotting import figure, curdoc

ROOT_LAYOUT = 'root'
COLUMN_SELECTOR_LAYOUT_NAME = 'column_selector'
SUMMARY_NAME = 'summary'
BAR_PLOT_NAME = 'plot1'
CATEGORY_LIMIT = 19


NCOV_DATASETS = [
    ('https://data.nextstrain.org/files/ncov/open/global/metadata.tsv.xz', 'ncov/open/global'),
    ('https://data.nextstrain.org/files/ncov/open/africa/metadata.tsv.xz', 'ncov/open/africa'),
    ('https://data.nextstrain.org/files/ncov/open/asia/metadata.tsv.xz', 'ncov/open/asia'),
    ('https://data.nextstrain.org/files/ncov/open/europe/metadata.tsv.xz', 'ncov/open/europe'),
    ('https://data.nextstrain.org/files/ncov/open/north-america/metadata.tsv.xz', 'ncov/open/north-america'),
    ('https://data.nextstrain.org/files/ncov/open/oceania/metadata.tsv.xz', 'ncov/open/oceania'),
    ('https://data.nextstrain.org/files/ncov/open/south-america/metadata.tsv.xz', 'ncov/open/south-america'),
    # TODO: handle ambiguous dates to support the following
    # ('https://data.nextstrain.org/files/workflows/mpox/metadata.tsv.gz', 'mpox'),
    # ('https://data.nextstrain.org/files/zika/metadata.tsv.zst', 'zika'),
    # ('https://data.nextstrain.org/files/workflows/measles/metadata.tsv.zst', 'measles'),
]


def process_tsv(read_csv_input):
    metadata = pd.read_csv(read_csv_input, delimiter='\t')
    # TODO: validate date column and values
    plot_per_month(metadata)

    replace_layout(SUMMARY_NAME, Div(name=SUMMARY_NAME, text=f"Number of rows: {len(metadata)}"))

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


def load_local_file(attr, _old_value, file_contents):
    assert attr == 'value'

    print('Loading metadata...')
    file = io.BytesIO(b64decode(file_contents))
    process_tsv(file)
    print('Successfully loaded metadata.')


def load_remote_file(attr, _old_value, url):
    assert attr == 'value'

    print(f'Loading dataset rom {url}...')
    # grab file
    process_tsv(url)
    print('Successfully loaded metadata.')


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


def replace_layout(name, new_layout, root_layout=None):
    if root_layout is None:
        root_layout = curdoc().get_model_by_name(ROOT_LAYOUT)

    children = root_layout.children
    old_layout = curdoc().get_model_by_name(name)
    for i, layout in enumerate(children):
        if layout == old_layout:
            children[i] = new_layout
            return
        elif hasattr(layout, 'children'):
            replace_layout(name, new_layout, root_layout=layout)


about_text = Div(text="<h1>Nextstrain Metadata Explorer</h1>")

file_input = FileInput(title="Select a TSV file", accept=".tsv")
file_input.on_change('value', load_local_file)

or_text = Div(text="OR")

dataset_selector = Select(
    name='ncov dataset',
    title='Load a public dataset',
    options=NCOV_DATASETS,
)
dataset_selector.on_change('value', load_remote_file)

column_selector = Select(
    name=COLUMN_SELECTOR_LAYOUT_NAME,
    title='Select column (select metadata first)',
    options=[],
    disabled=True,
)

summary = Div(name=SUMMARY_NAME, text="")

p = figure(name=BAR_PLOT_NAME, height=350)

curdoc().add_root(column(
    about_text,
    row(file_input, or_text, dataset_selector),
    column_selector,
    summary,
    p,
    name=ROOT_LAYOUT,
))

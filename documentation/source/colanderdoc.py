
from sphinx.util.compat import Directive
from docutils import nodes

import colander

# From http://stackoverflow.com/questions/452969/does-python-have-an-equivalent-to-java-class-forname
def get_class(kls):
	"""
	Helper function to get a class from its
	fully qualified name.

	:arg str kls: The class name to fetch.
	"""
	parts = kls.split('.')
	module = ".".join(parts[:-1])
	m = __import__( module )
	for comp in parts[1:]:
		m = getattr(m, comp)
	return m

class ColanderDocDirective(Directive):

	required_arguments = 1
	has_content = True

	def run(self):
		content = []

		# First, add a short description supplied by the directive.
		text = '\n'.join(self.content)
		text_node = nodes.paragraph(rawsource=text)
		# Parse the directive contents.
		self.state.nested_parse(self.content, self.content_offset, text_node)
		content.append(text_node)

		klass_name = self.arguments[0]
		klass = get_class(klass_name)

		definition_list = nodes.definition_list()

		# Now, go over the class and find and interogate all the properties.
		raw_text = ""
		for attribute in klass.__class_schema_nodes__:
			list_item = nodes.definition_list_item()

			# TODO: Make it parse in restructuredtext from the nodes themselves.
			term = nodes.term(text=attribute.name)

			# Add two classifiers; one for the type and the other
			# if it's required or optional.
			node_type = nodes.classifier(text=attribute.typ.__class__.__name__)
			required_text = 'Optional'
			if attribute.required:
				required_text = 'Required'
			required = nodes.classifier(text=required_text)

			# Set up the description, adding in full stops if needed.
			definition = nodes.definition()
			description_text = attribute.title
			if not attribute.title.endswith('.'):
				description_text += '.'
			description_text += ' ' + attribute.description
			if not description_text.endswith('.'):
				description_text += '.'

			description = nodes.paragraph(text=description_text)

			definition += description

			if attribute.default != colander.null:
				# There is a default set. Add it.
				default_text = "Default value: %s" % str(attribute.default)
				default = nodes.paragraph(text=default_text)

				definition += default

			list_item += term
			list_item += node_type
			list_item += required
			list_item += definition

			definition_list += list_item

		content.append(definition_list)

		content.append(nodes.paragraph(text="Original class: %s" % klass))

		return content

def setup(app):
	app.add_directive('colanderdoc', ColanderDocDirective)
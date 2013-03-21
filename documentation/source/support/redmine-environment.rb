# In file config/environment.rb

# Load the rails application
require File.expand_path('../application', __FILE__)

# Make sure there's no plugin in vendor/plugin before starting
vendor_plugins_dir = File.join(Rails.root, "vendor", "plugins")
if Dir.glob(File.join(vendor_plugins_dir, "*")).any?
  $stderr.puts "Plugins in vendor/plugins (#{vendor_plugins_dir}) are no longer allowed. " +
    "Please, put your Redmine plugins in the `plugins` directory at the root of your " +
    "Redmine directory (#{File.join(Rails.root, "plugins")})"
  exit 1
end

# For Paasmaker, determine the rails environment.
require 'paasmaker'
interface = Paasmaker::Interface.new(['paasmaker-placeholder.yml'])
ENV['RAILS_ENV'] = interface.get_rails_env('production')

# Store the interface into a global variable for later use.
$PAASMAKER_INTERFACE = interface

# Initialize the rails application
RedmineApp::Application.initialize!
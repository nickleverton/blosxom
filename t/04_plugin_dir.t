# blosxom standard $plugin_dir testing

use strict;
use Test::More tests => 1;
use Test::Differences;
use Cwd;
use IO::File;

my $blosxom_root = 'plugin_dir';
$blosxom_root = "t/$blosxom_root" if -d "t/$blosxom_root";
$blosxom_root = cwd . "/$blosxom_root";
die "cannot find root '$blosxom_root'" 
  unless -d $blosxom_root;

my $blosxom_config_dir = "$blosxom_root/config";
die "cannot find blosxom config dir '$blosxom_config_dir'" unless -d $blosxom_config_dir;
$ENV{BLOSXOM_CONFIG_DIR} = $blosxom_config_dir;

my $blosxom_cgi = "$blosxom_root/../../blosxom.cgi";
die "cannot find blosxom.cgi '$blosxom_cgi'" unless -f $blosxom_cgi;
die "blosxom.cgi '$blosxom_cgi' is not executable" unless -x $blosxom_cgi;

my $fh = IO::File->new("$blosxom_root/expected.html", 'r')
  or die "cannot open expected output file '$blosxom_root/expected.html': $!";
my $expected;
{
  local $/ = undef;
  $expected = <$fh>;
  $fh->close;
}

my $output = qx($blosxom_cgi);

eq_or_diff($output, $expected, 'html output ok');


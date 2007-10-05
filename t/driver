#!/usr/bin/perl

use strict;
use warnings;

use Test::More qw( no_plan );

use Cwd;
use YAML;
use IO::File;
use File::Find;
use File::Copy;
#use File::Touch;
use File::Basename;
use Test::Differences;

my $test = basename($0);
$test =~ s/^\d+_?//;
$test =~ s/\.t$//;

my $testdir = $test;
$testdir = "t/$testdir" if -d "t/$testdir";
$testdir = cwd . "/$testdir";
die "cannot find root '$testdir'" unless -d $testdir;

my $blosxom_config_dir = "$testdir/config";
die "cannot find blosxom config dir '$blosxom_config_dir'" unless -d $blosxom_config_dir;
$ENV{BLOSXOM_CONFIG_DIR} = $blosxom_config_dir;

my $blosxom_cgi = "$testdir/../../blosxom.cgi";
die "cannot find blosxom.cgi '$blosxom_cgi'" unless -f $blosxom_cgi;
die "blosxom.cgi '$blosxom_cgi' is not executable" unless -x $blosxom_cgi;

my $spec = YAML::LoadFile ("$testdir/spec.yaml") 
  or fail("$test - loading spec") and next;

touch_files("$testdir/data");

my %expected = ();

for (@{$spec->{tests}}) {
  my ($args, $output) = @$_;

  unless ($expected{$output}) {
    my $fh = IO::File->new("$testdir/$output", 'r')
      or die "cannot open expected output file '$output': $!";
    {
      local $/ = undef;
      $expected{$output} = <$fh>;
    }
    $fh->close;
  }

  my $got = qx($blosxom_cgi $args);

  eq_or_diff($got, $expected{$output}, "$test - got expected output for args [$args]", { style => 'Unified' });
}

sub touch_files {
  find( sub {
    if (/^(.*)\.(\d+)$/) {
      copy($_, $1);
      `touch -t $2 $1`;
    }
  },
  shift );
}

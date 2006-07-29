#!/usr/bin/perl

use strict;
use warnings;

use Test::More qw( no_plan );

use File::Copy;
use File::Compare;
use File::Find;
use Cwd;
use YAML;


my $orig_cwd = cwd();

opendir(my $dh, $orig_cwd) or die("Opendir failed: $!");

my @tests = grep { /^t-/ } readdir $dh;

for my $testdir (@tests) {
  my (undef, $test) = split /-/, $testdir, 2;
  
  chdir $testdir;
  my $cwd = cwd();

  my $spec = YAML::LoadFile ("spec.yaml");

  if (! $spec) {
    fail ("$test - loading spec");
    next;
  }

  my $success = 1;

  copy("../../blosxom.cgi", ".") or die("Copy failed: $!");
  chmod(0777, "blosxom.cgi");

  system("perl -pi -e 's{/Library/WebServer/Documents/blosxom}{$cwd/data}' blosxom.cgi") == 0
      or die "$!";

  touch_files ();

  for (@{$spec->{tests}}) {
    my ($args, $output) = @$_;

    system("./blosxom.cgi $args > ${output}.got") == 0
        or die "$!";

    if (ok(compare("${output}.got", $output) == 0, 
           "$test - Got expected output for args [$args]")) {
      unlink("${output}.got");
    } else {
      $success = 0;
    }
  }

  if ($success) {
    unlink("blosxom.cgi");
  }

  chdir $orig_cwd;
}



sub touch_files {
  find( sub {
    if (/^(.*)\.(\d+)$/) {
      copy($_, $1);
      `touch -t $2 $1`;
    }
  },
        "./data");
}
